import argparse
import logging
from pathlib import Path
from typing import Any, Final

from ruamel.yaml.comments import CommentedSeq

from pipeline_migration.yamleditor import EditYAMLEntry
from pipeline_migration.types import FilePath
from pipeline_migration.utils import YAMLStyle
from pipeline_migration.pipeline import PipelineFileOperation, iterate_files_or_dirs


logger = logging.getLogger("mod_task")

# TODO
SUBCMD_DESCRIPTION: Final = """\
TODO
"""

# TODO: if task doesn't exist, error or just warning?
class TaskNotFound(Exception):
    """Specified task doesn't exist in the pipeline"""


def register_cli(subparser) -> None:
    mod_task_parser = subparser.add_parser(
        "task",
        help="Update the specified Konflux task",
        description=SUBCMD_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    mod_task_parser.add_argument(
        "task_name",
        metavar="TASK-NAME",
        help="Konflux task name. This is the actual task name defined in "
        "konflux-ci/build-definitions. By default, this name is also used as the pipeline task "
        "name. If a trusted artifact task is being added, suffix -oci-ta is removed automatically "
        "from the name and the result is used as the pipeline task name. To specify a pipeline "
        "task name explicitly, use option --pipeline-task-name.",
    )
    mod_task_parser.add_argument(
        "-f",
        "--file-or-dir",
        dest="file_or_dir",
        action="append",
        default=[],
        help="Specify locations from where finding out pipelines to add task. "
        "A pipeline can be included in a PipelineRun or a single Pipeline definition. "
        "%(prog)s searches pipelines from given locations by rules, if files are specified, "
        "search just pipelines from them. If directories are specified, search YAML files from the "
        "first level of each one. If neither is specified, the location defaults to ./.tekton/ "
        "directory.",
    )
    mod_task_parser.add_argument(
        "-g",
        "--git-add",
        dest="git_add",
        action="store_true",
        help="Add the modified files to git index.",
    )

    subparser_mod = mod_task_parser.add_subparsers(title="subcommands to modify task", required=True)

    # add-param
    subparser_add_param = subparser_mod.add_parser(
        "add-param",
        help="Add the specified parameter to a task. If parameter already exists, it updates the value.",
    )
    subparser_add_param.add_argument(
        "param_name",
        help="parameter name",
        metavar="PARAM-NAME"
    )
    subparser_add_param.add_argument(
        "param_value",
        help="parameter value",
        metavar="PARAM-VALUE"
    )
    subparser_add_param.set_defaults(action=action_add_param)

    # remove-param
    subparser_remove_param = subparser_mod.add_parser(
        "remove-param",
        help="Remove the specified parameter from a task.",
    )
    subparser_remove_param.add_argument(
        "param_name",
        help="parameter name",
        metavar="PARAM-NAME"
    )

    subparser_remove_param.set_defaults(action=action_remove_param)


class ModTaskAddParamOperation(PipelineFileOperation):
    def __init__(
        self,
        task_name: str,
        param_name: str,
        param_value: str,  # TODO: array, object, string values
        git_add: bool = False,  # TODO
    ) -> None:
        self.task_name = task_name
        self.param_name = param_name
        self.param_value = param_value
        self.git_add = git_add

    def handle_pipeline_file(self, file_path: FilePath, loaded_doc: Any, style: YAMLStyle) -> None:
        tasks = loaded_doc["spec"]["tasks"]
        if self._add_param(tasks, ["spec", "tasks"], file_path):
            pass
            # TODO
            # if self.git_add:
            #    git_add(file_path)
            #    logger.info("%s is added to git index.", file_path)

    def handle_pipeline_run_file(
        self, file_path: FilePath, loaded_doc: Any, style: YAMLStyle
    ) -> None:
        tasks = loaded_doc["spec"]["pipelineSpec"]["tasks"]
        if self._add_param(tasks, ["spec", "pipelineSpec", "tasks"], file_path):
            pass
            # TODO
            # if self.git_add:
            #    git_add(file_path)
            #    logger.info("%s is added to git index.", file_path)

    def _add_param(self, tasks: CommentedSeq, path_prefix, pipeline_file: FilePath) -> bool:
        # TODO: flat structure
        path = path_prefix
        for index, task in enumerate(tasks):
            if task["name"] == self.task_name:
                path.append(index)

                # When params section doesn't exist
                if "params" not in task:
                    new_data = {"params": [{"name": self.param_name, "value": self.param_value}]}
                    yamledit = EditYAMLEntry(pipeline_file)
                    yamledit.insert(path, new_data)
                    return True

                path.append("params")
                for index_param, param in enumerate(task["params"]):
                    if param['name'] == self.param_name:
                        path.append(index_param)
                        if param['value'] != self.param_value:
                            param['value'] = self.param_value
                            yamledit = EditYAMLEntry(pipeline_file)
                            yamledit.replace(path, param)
                            return True
                        return False  # param task found and doesn't need replacement

                # param name doesn't exist
                new_data = {"name": self.param_name, "value": self.param_value}
                yamledit = EditYAMLEntry(pipeline_file)
                yamledit.insert(path, new_data)
                return True

        return False


def action_add_param(args) -> None:
    search_places = [path for path in args.file_or_dir if path]
    relative_tekton_dir = Path("./.tekton")
    if not search_places and relative_tekton_dir.exists():
        search_places = [str(relative_tekton_dir.absolute())]

    op = ModTaskAddParamOperation(args.task_name, args.param_name, args.param_value, git_add=args.git_add)
    for file_path in iterate_files_or_dirs(search_places):
        op.handle(str(file_path))


class ModTaskRemoveParamOperation(PipelineFileOperation):
    def __init__(
        self,
        task_name: str,
        param_name: str,
        git_add: bool = False,  # TODO
    ) -> None:
        self.task_name = task_name
        self.param_name = param_name
        self.git_add = git_add

    def handle_pipeline_file(self, file_path: FilePath, loaded_doc: Any, style: YAMLStyle) -> None:
        tasks = loaded_doc["spec"]["tasks"]
        if self._remove_param(tasks, ["spec", "tasks"], file_path):
            pass
            # TODO
            # if self.git_add:
            #    git_add(file_path)
            #    logger.info("%s is added to git index.", file_path)

    def handle_pipeline_run_file(
        self, file_path: FilePath, loaded_doc: Any, style: YAMLStyle
    ) -> None:
        tasks = loaded_doc["spec"]["pipelineSpec"]["tasks"]
        if self._remove_param(tasks, ["spec", "pipelineSpec", "tasks"], file_path):
            pass
            # TODO
            # if self.git_add:
            #    git_add(file_path)
            #    logger.info("%s is added to git index.", file_path)

    def _remove_param(self, tasks: CommentedSeq, path_prefix, pipeline_file: FilePath) -> bool:
        # TODO: flat structure
        path = path_prefix
        for index, task in enumerate(tasks):
            if task["name"] == self.task_name:
                path.append(index)

                # When params section doesn't exist
                if "params" not in task:
                    return False  # nothing to do

                path.append("params")
                for index_param, param in enumerate(task["params"]):
                    if param['name'] == self.param_name:
                        path.append(index_param)
                        yamledit = EditYAMLEntry(pipeline_file)
                        yamledit.delete(path)
                        return True

                return False  # param doesn't exist, nothing to do

        return False


def action_remove_param(args) -> None:
    search_places = [path for path in args.file_or_dir if path]
    relative_tekton_dir = Path("./.tekton")
    if not search_places and relative_tekton_dir.exists():
        search_places = [str(relative_tekton_dir.absolute())]

    op = ModTaskRemoveParamOperation(args.task_name, args.param_name, git_add=args.git_add)
    for file_path in iterate_files_or_dirs(search_places):
        op.handle(str(file_path))