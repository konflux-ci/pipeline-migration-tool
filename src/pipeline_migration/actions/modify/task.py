import argparse
import logging
from pathlib import Path
from typing import Any, Final

from ruamel.yaml.comments import CommentedSeq

from pipeline_migration.yamleditor import EditYAMLEntry, YAMLPath
from pipeline_migration.types import FilePath
from pipeline_migration.utils import YAMLStyle, git_add
from pipeline_migration.pipeline import PipelineFileOperation, iterate_files_or_dirs


logger = logging.getLogger("modify.task")


SUBCMD_DESCRIPTION: Final = """\
The following are several examples with a Konflux task push-dockerfile:

* Modify a task within relative .tekton/ directory.

    cd /path/to/repo
    pmt modify task push-dockerfile add-param new-param new-value

* Modify task in multiple pipelines in several repositories:

    pmt modify task push-dockerfile \\
        -f /path/to/repo1/.tekton/pr.yaml -f /path/to/repo2/.tekton/push.yaml \\
        add-param new-param new-value

* Supported task modifications:
   - add-param: adds a new param to the task (or updates existing)
   - remove-param: removes the specified param from the task
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
    subparser_mod = mod_task_parser.add_subparsers(
        title="subcommands to modify task", required=True
    )

    # add-param
    subparser_add_param = subparser_mod.add_parser(
        "add-param",
        help="Add the specified parameter to a task. If parameter already exists, "
        "it updates the value.",
    )
    subparser_add_param.add_argument("param_name", help="parameter name", metavar="PARAM-NAME")
    subparser_add_param.add_argument("param_value", help="parameter value", metavar="PARAM-VALUE")
    subparser_add_param.set_defaults(action=action_add_param)

    # remove-param
    subparser_remove_param = subparser_mod.add_parser(
        "remove-param",
        help="Remove the specified parameter from a task.",
    )
    subparser_remove_param.add_argument("param_name", help="parameter name", metavar="PARAM-NAME")

    subparser_remove_param.set_defaults(action=action_remove_param)


class ModTaskAddParamOperation(PipelineFileOperation):
    def __init__(
        self,
        task_name: str,
        param_name: str,
        param_value: str,  # TODO: array, object, string values
        git_add: bool = False,
    ) -> None:
        self.task_name = task_name
        self.param_name = param_name
        self.param_value = param_value
        self.git_add = git_add

    def handle_pipeline_file(self, file_path: FilePath, loaded_doc: Any, style: YAMLStyle) -> None:
        tasks = loaded_doc["spec"]["tasks"]
        if self._add_param(tasks, ["spec", "tasks"], file_path, style) and self.git_add:
            git_add(file_path)
            logger.info("%s is added to git index.", file_path)

    def handle_pipeline_run_file(
        self, file_path: FilePath, loaded_doc: Any, style: YAMLStyle
    ) -> None:
        tasks = loaded_doc["spec"]["pipelineSpec"]["tasks"]
        if (
            self._add_param(tasks, ["spec", "pipelineSpec", "tasks"], file_path, style)
            and self.git_add
        ):
            git_add(file_path)
            logger.info("%s is added to git index.", file_path)

    def _add_param(
        self, tasks: CommentedSeq, path_prefix: YAMLPath, pipeline_file: FilePath, style: YAMLStyle
    ) -> bool:
        """Private function that adds parameter into task if needed (or create the whole params
        section if missing)

        If parameter with the same value exist, this is a no-op

        Given the tasks are located in different locations in pipeline VS pipelineRun objects,
        we need path_prefix consisting of path to the tasks in yaml
        """
        path = path_prefix
        for index, task in enumerate(tasks):
            if task.get("name", "") != self.task_name:
                continue

            path.append(index)

            # When params section doesn't exist
            if "params" not in task:
                new_data_with_parent = {
                    "params": [{"name": self.param_name, "value": self.param_value}]
                }
                yamledit = EditYAMLEntry(pipeline_file, style=style)
                yamledit.insert(path, new_data_with_parent)
                return True

            path.append("params")
            for index_param, param in enumerate(task["params"]):
                if param["name"] == self.param_name:
                    path.append(index_param)
                    if param["value"] != self.param_value:
                        param["value"] = self.param_value
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

    op = ModTaskAddParamOperation(
        args.task_name, args.param_name, args.param_value, git_add=args.git_add
    )
    for file_path in iterate_files_or_dirs(search_places):
        op.handle(str(file_path))


class ModTaskRemoveParamOperation(PipelineFileOperation):
    def __init__(
        self,
        task_name: str,
        param_name: str,
        git_add: bool = False,
    ) -> None:
        self.task_name = task_name
        self.param_name = param_name
        self.git_add = git_add

    def handle_pipeline_file(self, file_path: FilePath, loaded_doc: Any, style: YAMLStyle) -> None:
        tasks = loaded_doc["spec"]["tasks"]
        if self._remove_param(tasks, ["spec", "tasks"], file_path, style):
            if self.git_add:
                git_add(file_path)
                logger.info("%s is added to git index.", file_path)

    def handle_pipeline_run_file(
        self, file_path: FilePath, loaded_doc: Any, style: YAMLStyle
    ) -> None:
        tasks = loaded_doc["spec"]["pipelineSpec"]["tasks"]
        if self._remove_param(tasks, ["spec", "pipelineSpec", "tasks"], file_path, style):
            if self.git_add:
                git_add(file_path)
                # TODO: when git fails, it shows error and the info that
                # it was added at the same time
                logger.info("%s is added to git index.", file_path)

    def _remove_param(
        self, tasks: CommentedSeq, path_prefix: YAMLPath, pipeline_file: FilePath, style: YAMLStyle
    ) -> bool:
        """Private function that removes parameter from task if needed

        If parameter with the same name doesn't exist, this is a no-op

        Given the tasks are located in different locations in pipeline VS pipelineRun objects,
        we need path_prefix consisting of path to the tasks in yaml
        """
        path = path_prefix
        for index, task in enumerate(tasks):
            if task.get("name", "") != self.task_name:
                continue

            path.append(index)

            # When params section doesn't exist
            if "params" not in task:
                return False  # nothing to do

            path.append("params")
            for index_param, param in enumerate(task["params"]):
                if param["name"] == self.param_name:
                    path.append(index_param)
                    yamledit = EditYAMLEntry(pipeline_file, style=style)
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
