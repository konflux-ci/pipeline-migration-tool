from abc import abstractmethod
import argparse
import copy
import logging
from typing import Any, Final

from ruamel.yaml.comments import CommentedSeq

from pipeline_migration.yamleditor import EditYAMLEntry, YAMLPath
from pipeline_migration.types import FilePath
from pipeline_migration.utils import YAMLStyle, load_yaml
from pipeline_migration.pipeline import PipelineFileOperation
from pipeline_migration.actions.add_task import get_task_bundle_reference
from pipeline_migration.actions.modify.common import run_modify
from pipeline_migration.actions.modify.common import (
    ParamType,
    get_nested,
)

logger = logging.getLogger("modify.task")


SUBCMD_DESCRIPTION: Final = """\
The following are several examples with a Konflux task push-dockerfile:

* Modify a task within relative .tekton/ directory.

    cd /path/to/repo
    pmt modify task push-dockerfile add-param new-param new-value

* Modify task in multiple pipelines in several repositories:

    pmt modify \\
        -f /path/to/repo1/.tekton/pr.yaml -f /path/to/repo2/.tekton/push.yaml \\
        task push-dockerfile \\
        add-param new-param new-value

* Add array of values.

    cd /path/to/repo
    pmt modify task push-dockerfile add-param -t array new-param new-value1 new-value2

    Note: if the param name exist current values will be replaced, not appended

* Rename a task:

    pmt modify task clair-scan rename roxctl-scan

* Rename a task and update the taskRef resolver name param:

    pmt modify task clair-scan rename roxctl-scan --task-ref-name task-roxctl-scan

* Set the bundle for a task:

    pmt modify task buildah set-bundle quay.io/org/task-buildah:0.2@sha256:abc123

* Set the bundle and update the taskRef resolver name param:

    pmt modify task buildah set-bundle quay.io/org/task-buildah:0.2@sha256:abc123 \\
        --task-ref-name task-buildah

* Supported task modifications:
   - add-param: adds a new param to the task (or updates existing)
   - remove-param: removes the specified param from the task
   - matrix-add-param: adds a new matrix param to the task (or updates existing)
   - matrix-remove-param: removes the specified matrix param from the task
   - rename: renames the task in the pipeline
   - set-bundle: sets the bundle in the taskRef resolver params
"""


class TaskNotFoundError(Exception):
    """Task of the given name not found"""


class DuplicateTaskNameError(Exception):
    """Raised when a rename would create a duplicate task name in the pipeline."""


def _update_task_ref_name(
    task_name: str,
    task_ref_name: str,
    ref_params: list,
    task_path: YAMLPath,
    pipeline_file: FilePath,
    style: YAMLStyle,
) -> None:
    """Update the 'name' param value inside taskRef.params to task_ref_name.

    Logs a warning and does nothing if the 'name' param is not present in ref_params.
    """
    for param_index, param in enumerate(ref_params):
        if param.get("name") == "name":
            yamledit = EditYAMLEntry(pipeline_file, style=style)
            yamledit.replace(
                task_path + ["taskRef", "params", param_index, "value"],
                task_ref_name,
            )
            logger.info(
                "task '%s' in '%s': taskRef name updated to '%s'",
                task_name,
                pipeline_file,
                task_ref_name,
            )
            break
    else:
        logger.warning(
            "task '%s' in '%s': taskRef has no 'name' param, " "skipping task-ref-name update",
            task_name,
            pipeline_file,
        )


class TaskBase(PipelineFileOperation):
    """Base class for task handling"""

    def __init__(self, task_name: str):
        super().__init__()
        self.task_name = task_name

    @abstractmethod
    def _do_action(
        self, tasks: CommentedSeq, path_prefix: YAMLPath, pipeline_file: FilePath, style: YAMLStyle
    ):
        """Method where the real YAML change is happening"""
        raise NotImplementedError

    def handle_pipeline_file(self, file_path: FilePath, loaded_doc: Any, style: YAMLStyle) -> None:
        """Apply the task modification to a Pipeline file."""
        yaml_paths = [
            ["spec", "tasks"],
            ["spec", "finally"],
        ]
        self._handle_paths(yaml_paths, file_path, loaded_doc, style)

    def handle_pipeline_run_file(
        self, file_path: FilePath, loaded_doc: Any, style: YAMLStyle
    ) -> None:
        """Apply the task modification to a PipelineRun file."""
        yaml_paths = [
            ["spec", "pipelineSpec", "tasks"],
            ["spec", "pipelineSpec", "finally"],
        ]
        self._handle_paths(yaml_paths, file_path, loaded_doc, style)

    def _handle_paths(
        self, yaml_paths: list[list[str]], file_path: FilePath, loaded_doc: Any, style: YAMLStyle
    ):
        not_found_task = [False] * len(yaml_paths)

        for index, yaml_path in enumerate(yaml_paths):
            # check if path exist
            try:
                tmp_doc = get_nested(copy.copy(loaded_doc), yaml_path)
            except KeyError:
                not_found_task[index] = True
                continue

            try:
                self._do_action(tmp_doc, yaml_path, file_path, style)
            except TaskNotFoundError:
                not_found_task[index] = True

        if all(not_found_task):
            logger.warning(
                "task '%s' does not exist in '%s'",
                self.task_name,
                file_path,
            )


def register_cli(subparser) -> None:
    """Register the 'task' subcommand and its sub-actions on the CLI parser."""
    mod_task_parser = subparser.add_parser(
        "task",
        help="Update the specified Konflux task",
        description=SUBCMD_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    mod_task_parser.add_argument(
        "task_name",
        metavar="TASK-NAME",
        help="Pipeline task name in pipeline/pipeline run YAML file.",
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
    subparser_add_param.add_argument(
        "param_value", nargs="+", help="parameter values", metavar="PARAM-VALUE"
    )
    subparser_add_param.add_argument(
        "-t",
        "--type",
        dest="param_type",
        help="parameter type (Default: %(default)s)",
        type=ParamType,
        choices=list(ParamType),
        default=ParamType.string,
    )
    subparser_add_param.set_defaults(action=action_add_param)

    # remove-param
    subparser_remove_param = subparser_mod.add_parser(
        "remove-param",
        help="Remove the specified parameter from a task.",
    )
    subparser_remove_param.add_argument("param_name", help="parameter name", metavar="PARAM-NAME")

    subparser_remove_param.set_defaults(action=action_remove_param)

    # matrix-add-param
    subparser_add_param = subparser_mod.add_parser(
        "matrix-add-param",
        help="Add the specified parameter to a task matrix. If parameter already exists, "
        "it updates the value.",
    )
    subparser_add_param.add_argument("param_name", help="parameter name", metavar="PARAM-NAME")
    subparser_add_param.add_argument(
        "param_value", nargs="+", help="parameter values", metavar="PARAM-VALUE"
    )
    subparser_add_param.add_argument(
        "-t",
        "--type",
        dest="param_type",
        help="parameter type (Default: %(default)s)",
        type=ParamType,
        choices=list(ParamType),
        default=ParamType.string,
    )
    subparser_add_param.set_defaults(action=action_matrix_add_param)

    # matrix-remove-param
    subparser_remove_param = subparser_mod.add_parser(
        "matrix-remove-param",
        help="Remove the specified parameter from a task matrix.",
    )
    subparser_remove_param.add_argument("param_name", help="parameter name", metavar="PARAM-NAME")

    subparser_remove_param.set_defaults(action=action_matrix_remove_param)

    # rename
    subparser_rename = subparser_mod.add_parser(
        "rename",
        help="Rename the task in the pipeline.",
    )
    subparser_rename.add_argument("new_name", help="new task name", metavar="NEW-NAME")
    subparser_rename.add_argument(
        "-r",
        "--task-ref-name",
        metavar="REF-NAME",
        dest="task_ref_name",
        default=None,
        help="New value for the 'name' entry in taskRef.params (the actual task name inside "
        "the bundle resolver). If omitted, taskRef.params is left unchanged.",
    )
    subparser_rename.set_defaults(action=action_rename)

    # set-bundle
    subparser_set_bundle = subparser_mod.add_parser(
        "set-bundle",
        help="Set the bundle in the taskRef resolver params.",
    )
    subparser_set_bundle.add_argument(
        "bundle_ref",
        type=get_task_bundle_reference,
        help="new bundle reference (e.g. quay.io/org/task-foo:0.1@sha256:...)",
        metavar="BUNDLE-REF",
    )
    subparser_set_bundle.add_argument(
        "-r",
        "--task-ref-name",
        metavar="REF-NAME",
        dest="task_ref_name",
        default=None,
        help="New value for the 'name' entry in taskRef.params. If omitted, the name param "
        "is left unchanged.",
    )
    subparser_set_bundle.set_defaults(action=action_set_bundle)


class ModTaskAddParamOperation(TaskBase):
    """Operation that adds or updates a parameter on a pipeline task."""

    def __init__(
        self,
        task_name: str,
        param_name: str,
        param_value: str | list[str],
    ) -> None:
        super().__init__(task_name)
        self.param_name = param_name
        self.param_value = param_value

    def _do_action(
        self, tasks: CommentedSeq, path_prefix: YAMLPath, pipeline_file: FilePath, style: YAMLStyle
    ) -> bool:
        """Private function that adds parameter into task if needed (or create the whole params
        section if missing)

        If parameter with the same value exist, this is a no-op

        Given the tasks are located in different locations in pipeline VS pipelineRun objects,
        we need path_prefix consisting of path to the tasks in yaml
        """
        path = path_prefix
        task_found = False
        for index, task in enumerate(tasks):
            if task.get("name", "") != self.task_name:
                continue

            task_found = True
            path.append(index)

            # When params section doesn't exist
            if "params" not in task:
                new_data_with_parent = {
                    "params": [{"name": self.param_name, "value": self.param_value}]
                }
                logger.info(
                    (
                        "task '%s' in '%s': param '%s' will be created (params attribute "
                        "will be created)"
                    ),
                    self.task_name,
                    pipeline_file,
                    self.param_name,
                )
                yamledit = EditYAMLEntry(pipeline_file, style=style)
                yamledit.insert(path, new_data_with_parent)
                return True

            path.append("params")
            for index_param, param in enumerate(task["params"]):
                if param["name"] == self.param_name:
                    path.append(index_param)
                    if (
                        param["value"] is None
                        or (
                            isinstance(self.param_value, str) and param["value"] != self.param_value
                        )
                        or (
                            # assume that order of params doesn't matter
                            set(self.param_value)
                            != set(param["value"])
                        )
                    ):
                        param["value"] = self.param_value
                        logger.info(
                            "task '%s' in '%s': param '%s' will be updated",
                            self.task_name,
                            pipeline_file,
                            self.param_name,
                        )
                        yamledit = EditYAMLEntry(pipeline_file, style=style)
                        yamledit.replace(path, param)
                        return True

                    logger.info(
                        "task '%s' in '%s': param '%s' already has required values",
                        self.task_name,
                        pipeline_file,
                        self.param_name,
                    )
                    return False  # param task found and doesn't need replacement

            # param name doesn't exist
            new_data = {"name": self.param_name, "value": self.param_value}
            logger.info(
                "task '%s' in '%s': param '%s' will be created",
                self.task_name,
                pipeline_file,
                self.param_name,
            )
            yamledit = EditYAMLEntry(pipeline_file, style=style)
            yamledit.insert(path, new_data)
            return True

        if not task_found:
            raise TaskNotFoundError

        return False


def action_add_param(args) -> None:
    """CLI action handler to add a parameter to a task in pipeline files."""
    value = args.param_value
    if args.param_type == ParamType.string:
        if len(value) > 1:

            raise RuntimeError("Param value must be only one item with string type")
        value = value[0]  # extract value when type is string

    op = ModTaskAddParamOperation(args.task_name, args.param_name, value)
    run_modify(op, args)


class ModTaskRemoveParamOperation(TaskBase):
    """Operation that removes a parameter from a pipeline task."""

    def __init__(
        self,
        task_name: str,
        param_name: str,
    ) -> None:
        super().__init__(task_name)
        self.task_name = task_name
        self.param_name = param_name

    def _do_action(
        self, tasks: CommentedSeq, path_prefix: YAMLPath, pipeline_file: FilePath, style: YAMLStyle
    ) -> bool:
        """Private function that removes parameter from task if needed

        If parameter with the same name doesn't exist, this is a no-op

        Given the tasks are located in different locations in pipeline VS pipelineRun objects,
        we need path_prefix consisting of path to the tasks in yaml
        """
        path = path_prefix
        task_found = False
        for index, task in enumerate(tasks):
            if task.get("name", "") != self.task_name:
                continue

            task_found = True
            path.append(index)

            # When params section doesn't exist
            if "params" not in task:
                logger.info(
                    "task '%s' in '%s': param '%s' does not exist, nothing to remove",
                    self.task_name,
                    pipeline_file,
                    self.param_name,
                )
                return False  # nothing to do

            path.append("params")
            for index_param, param in enumerate(task["params"]):
                if param["name"] == self.param_name:
                    path.append(index_param)
                    logger.info(
                        "task '%s' in '%s': param '%s' will be removed",
                        self.task_name,
                        pipeline_file,
                        self.param_name,
                    )
                    yamledit = EditYAMLEntry(pipeline_file, style=style)
                    yamledit.delete(path)
                    return True

            return False  # param doesn't exist, nothing to do

        if not task_found:
            raise TaskNotFoundError

        return False


def action_remove_param(args) -> None:
    """CLI action handler to remove a parameter from a task in pipeline files."""
    op = ModTaskRemoveParamOperation(args.task_name, args.param_name)
    run_modify(op, args)


class ModTaskMatrixAddParamOperation(TaskBase):
    """Operation that adds or updates a matrix parameter on a pipeline task."""

    def __init__(
        self,
        task_name: str,
        param_name: str,
        param_value: str | list[str],
    ) -> None:
        super().__init__(task_name)
        self.param_name = param_name
        self.param_value = param_value

    def _do_action(
        self, tasks: CommentedSeq, path_prefix: YAMLPath, pipeline_file: FilePath, style: YAMLStyle
    ) -> bool:
        """Private function that adds parameter into task if needed (or create the whole params
        section if missing)

        If parameter with the same value exist, this is a no-op

        Given the tasks are located in different locations in pipeline VS pipelineRun objects,
        we need path_prefix consisting of path to the tasks in yaml
        """
        path = path_prefix
        task_found = False
        for index, task in enumerate(tasks):
            if task.get("name", "") != self.task_name:
                continue

            task_found = True
            path.append(index)

            # When matrix section doesn't exist
            if "matrix" not in task:
                new_data_with_matrix = {
                    "matrix": {"params": [{"name": self.param_name, "value": self.param_value}]}
                }
                logger.info(
                    (
                        "task '%s' in '%s': param '%s' will be created (matrix attribute "
                        "will be created)"
                    ),
                    self.task_name,
                    pipeline_file,
                    self.param_name,
                )
                yamledit = EditYAMLEntry(pipeline_file, style=style)
                yamledit.insert(path, new_data_with_matrix)
                return True

            matrix = task["matrix"]
            path.append("matrix")
            # When params section doesn't exist
            if "params" not in matrix:
                new_data_with_parent = {
                    "params": [{"name": self.param_name, "value": self.param_value}]
                }
                logger.info(
                    (
                        "task '%s' in '%s': param '%s' will be created (params attribute "
                        "will be created)"
                    ),
                    self.task_name,
                    pipeline_file,
                    self.param_name,
                )
                yamledit = EditYAMLEntry(pipeline_file, style=style)
                yamledit.insert(path, new_data_with_parent)
                return True

            path.append("params")
            for index_param, param in enumerate(matrix["params"]):
                if param["name"] == self.param_name:
                    path.append(index_param)
                    if (
                        param["value"] is None
                        or (
                            isinstance(self.param_value, str) and param["value"] != self.param_value
                        )
                        or (
                            # assume that order of params doesn't matter
                            set(self.param_value)
                            != set(param["value"])
                        )
                    ):
                        param["value"] = self.param_value
                        logger.info(
                            "task '%s' in '%s': param '%s' will be updated",
                            self.task_name,
                            pipeline_file,
                            self.param_name,
                        )
                        yamledit = EditYAMLEntry(pipeline_file)
                        yamledit.replace(path, param)
                        return True

                    logger.info(
                        "task '%s' in '%s': param '%s' already has required values",
                        self.task_name,
                        pipeline_file,
                        self.param_name,
                    )
                    return False  # param task found and doesn't need replacement

            # param name doesn't exist
            new_data = {"name": self.param_name, "value": self.param_value}
            logger.info(
                "task '%s' in '%s': param '%s' will be created",
                self.task_name,
                pipeline_file,
                self.param_name,
            )
            yamledit = EditYAMLEntry(pipeline_file)
            yamledit.insert(path, new_data)
            return True

        if not task_found:
            raise TaskNotFoundError

        return False


def action_matrix_add_param(args) -> None:
    """CLI action handler to add a matrix parameter to a task in pipeline files."""
    value = args.param_value
    if args.param_type == ParamType.string:
        if len(value) > 1:

            raise RuntimeError("Param value must be only one item with string type")
        value = value[0]  # extract value when type is string

    op = ModTaskMatrixAddParamOperation(args.task_name, args.param_name, value)
    run_modify(op, args)


class ModTaskMatrixRemoveParamOperation(TaskBase):
    """Operation that removes a matrix parameter from a pipeline task."""

    def __init__(
        self,
        task_name: str,
        param_name: str,
    ) -> None:
        super().__init__(task_name)
        self.task_name = task_name
        self.param_name = param_name

    def _do_action(
        self, tasks: CommentedSeq, path_prefix: YAMLPath, pipeline_file: FilePath, style: YAMLStyle
    ) -> bool:
        """Private function that removes parameter from task if needed

        If parameter with the same name doesn't exist, this is a no-op

        Given the tasks are located in different locations in pipeline VS pipelineRun objects,
        we need path_prefix consisting of path to the tasks in yaml
        """
        path = path_prefix
        task_found = False
        for index, task in enumerate(tasks):
            if task.get("name", "") != self.task_name:
                continue

            task_found = True
            path.append(index)

            # When matrix doesn't exist
            if "matrix" not in task:
                logger.info(
                    "task '%s' in '%s': matrix does not exist, nothing to remove",
                    self.task_name,
                    pipeline_file,
                )
                return False  # nothing to do

            matrix = task["matrix"]
            path.append("matrix")

            # When params section doesn't exist
            if "params" not in matrix:
                logger.info(
                    "task '%s' in '%s': param '%s' does not exist in the matrix, nothing to remove",
                    self.task_name,
                    pipeline_file,
                    self.param_name,
                )
                return False  # nothing to do

            path.append("params")
            for index_param, param in enumerate(matrix["params"]):
                if param["name"] == self.param_name:
                    path.append(index_param)
                    logger.info(
                        "task '%s' in '%s': param '%s' will be removed from the matrix",
                        self.task_name,
                        pipeline_file,
                        self.param_name,
                    )
                    yamledit = EditYAMLEntry(pipeline_file, style=style)
                    yamledit.delete(path)
                    return True

            return False  # param doesn't exist, nothing to do

        if not task_found:
            raise TaskNotFoundError

        return False


def action_matrix_remove_param(args) -> None:
    """CLI action handler to remove a matrix parameter from a task in pipeline files."""
    op = ModTaskMatrixRemoveParamOperation(args.task_name, args.param_name)
    run_modify(op, args)


class ModTaskRenameOperation(TaskBase):
    """Operation that renames a pipeline task and optionally updates its taskRef resolver name."""

    def __init__(
        self,
        task_name: str,
        new_name: str,
        task_ref_name: str | None = None,
    ) -> None:
        super().__init__(task_name)
        self.new_name = new_name
        self.task_ref_name = task_ref_name

    def _do_action(
        self, tasks: CommentedSeq, path_prefix: YAMLPath, pipeline_file: FilePath, style: YAMLStyle
    ) -> bool:
        for index, task in enumerate(tasks):
            if task.get("name", "") != self.task_name:
                continue

            task_path = list(path_prefix) + [index]

            yamledit = EditYAMLEntry(pipeline_file, style=style)
            yamledit.replace(task_path + ["name"], self.new_name)
            logger.info(
                "task '%s' in '%s': renamed to '%s'",
                self.task_name,
                pipeline_file,
                self.new_name,
            )

            if self.task_ref_name is not None:
                task_ref = task.get("taskRef", {})
                _update_task_ref_name(
                    self.new_name,
                    self.task_ref_name,
                    task_ref.get("params", []),
                    task_path,
                    pipeline_file,
                    style,
                )

            return True

        raise TaskNotFoundError

    def _check_new_name_is_available(
        self, loaded_doc: Any, task_paths: list[list[str]], file_path: FilePath
    ) -> None:
        """Raise DuplicateTaskNameError if new_name is already used by a different task."""
        for path in task_paths:
            try:
                tmp = get_nested(loaded_doc, path)
            except KeyError:
                continue
            for task in tmp:
                name = task.get("name", "")
                if name == self.new_name and name != self.task_name:
                    raise DuplicateTaskNameError(
                        f"cannot rename task '{self.task_name}' to '{self.new_name}' "
                        f"in '{file_path}': a task named '{self.new_name}' already exists"
                    )

    def _update_run_after_refs(
        self, file_path: FilePath, style: YAMLStyle, task_paths: list[list[str]]
    ) -> None:
        """Replace occurrences of the old task name with the new name in all runAfter lists."""
        for path_prefix in task_paths:
            doc = load_yaml(file_path, style)
            try:
                tasks = get_nested(doc, path_prefix)
            except KeyError:
                continue

            for task_index, task in enumerate(tasks):
                run_after = task.get("runAfter", [])
                if self.task_name not in run_after:
                    continue

                new_run_after = [
                    self.new_name if name == self.task_name else name for name in run_after
                ]
                yamledit = EditYAMLEntry(file_path, style=style)
                yamledit.replace(list(path_prefix) + [task_index, "runAfter"], new_run_after)
                logger.info(
                    "task '%s' in '%s': runAfter updated '%s' -> '%s'",
                    task.get("name"),
                    file_path,
                    self.task_name,
                    self.new_name,
                )

    def handle_pipeline_file(self, file_path: FilePath, loaded_doc: Any, style: YAMLStyle) -> None:
        task_paths: list[list[str]] = [["spec", "tasks"], ["spec", "finally"]]
        self._check_new_name_is_available(loaded_doc, task_paths, file_path)
        super().handle_pipeline_file(file_path, loaded_doc, style)
        self._update_run_after_refs(file_path, style, task_paths)

    def handle_pipeline_run_file(
        self, file_path: FilePath, loaded_doc: Any, style: YAMLStyle
    ) -> None:
        task_paths: list[list[str]] = [
            ["spec", "pipelineSpec", "tasks"],
            ["spec", "pipelineSpec", "finally"],
        ]
        self._check_new_name_is_available(loaded_doc, task_paths, file_path)
        super().handle_pipeline_run_file(file_path, loaded_doc, style)
        self._update_run_after_refs(file_path, style, task_paths)


def action_rename(args) -> None:
    """CLI action handler to rename a task in pipeline files."""
    op = ModTaskRenameOperation(args.task_name, args.new_name, args.task_ref_name)
    try:
        run_modify(op, args)
    except DuplicateTaskNameError as e:
        raise SystemExit(f"error: {e}") from e


class ModTaskSetBundleOperation(TaskBase):
    """Operation that sets the bundle param in taskRef.params and optionally updates the name."""

    def __init__(
        self,
        task_name: str,
        bundle_ref: str,
        task_ref_name: str | None = None,
    ) -> None:
        super().__init__(task_name)
        self.bundle_ref = bundle_ref
        self.task_ref_name = task_ref_name

    def _do_action(
        self, tasks: CommentedSeq, path_prefix: YAMLPath, pipeline_file: FilePath, style: YAMLStyle
    ) -> bool:
        for index, task in enumerate(tasks):
            if task.get("name", "") != self.task_name:
                continue

            task_path = list(path_prefix) + [index]
            task_ref = task.get("taskRef", {})
            ref_params = task_ref.get("params", [])

            if not ref_params:
                logger.warning(
                    "task '%s' in '%s': taskRef has no params, skipping set-bundle",
                    self.task_name,
                    pipeline_file,
                )
                return False

            bundle_index = None
            for param_index, param in enumerate(ref_params):
                if param.get("name") == "bundle":
                    bundle_index = param_index
                    break

            if bundle_index is None:
                logger.warning(
                    "task '%s' in '%s': taskRef has no 'bundle' param, skipping set-bundle",
                    self.task_name,
                    pipeline_file,
                )
                return False

            if ref_params[bundle_index].get("value") != self.bundle_ref:
                yamledit = EditYAMLEntry(pipeline_file, style=style)
                yamledit.replace(
                    task_path + ["taskRef", "params", bundle_index, "value"],
                    self.bundle_ref,
                )
                logger.info(
                    "task '%s' in '%s': bundle updated to '%s'",
                    self.task_name,
                    pipeline_file,
                    self.bundle_ref,
                )
            else:
                logger.info(
                    "task '%s' in '%s': bundle already set to required value",
                    self.task_name,
                    pipeline_file,
                )

            if self.task_ref_name is not None:
                _update_task_ref_name(
                    self.task_name,
                    self.task_ref_name,
                    ref_params,
                    task_path,
                    pipeline_file,
                    style,
                )

            return True

        raise TaskNotFoundError


def action_set_bundle(args) -> None:
    """CLI action handler to set the bundle in taskRef.params for a task in pipeline files."""
    op = ModTaskSetBundleOperation(args.task_name, args.bundle_ref, args.task_ref_name)
    run_modify(op, args)
