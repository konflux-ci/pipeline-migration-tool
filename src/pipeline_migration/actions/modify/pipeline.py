import argparse
import logging
from enum import Enum
from pathlib import Path
from typing import Any, Final, List

from pipeline_migration.yamleditor import EditYAMLEntry, YAMLPath
from pipeline_migration.types import FilePath
from pipeline_migration.utils import YAMLStyle
from pipeline_migration.pipeline import PipelineFileOperation, iterate_files_or_dirs

logger = logging.getLogger("modify.pipeline")


SUBCMD_DESCRIPTION: Final = """\
The following are several examples of pipeline parameter modifications:

* Add a pipeline parameter within relative .tekton/ directory.

    cd /path/to/repo
    pmt modify pipeline add-param my-param

* Add a pipeline parameter with a default value:

    pmt modify pipeline add-param my-param --default my-value

* Add a pipeline parameter with a default value and type:

    pmt modify pipeline add-param my-param --default my-value --type string

* Add a pipeline parameter with array type and multiple default values:

    pmt modify pipeline add-param my-param --type array --default val1 val2

* Update an existing pipeline parameter's default value:

    pmt modify pipeline update-param my-param --default new-value

* Remove a pipeline parameter:

    pmt modify pipeline remove-param my-param

* Modify pipeline parameters in specific files:

    pmt modify \\
        -f /path/to/repo1/.tekton/pr.yaml -f /path/to/repo2/.tekton/push.yaml \\
        pipeline add-param my-param --default my-value

* Supported pipeline modifications:
   - add-param: adds a new param to the pipeline (or updates existing)
   - update-param: updates an existing param's default value
   - remove-param: removes the specified param from the pipeline
"""


class ParamType(Enum):
    string = "string"
    array = "array"

    def __str__(self):
        return self.value


def register_cli(subparser) -> None:
    mod_pipeline_parser = subparser.add_parser(
        "pipeline",
        help="Modify pipeline-level parameters",
        description=SUBCMD_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparser_mod = mod_pipeline_parser.add_subparsers(
        title="subcommands to modify pipeline parameters", required=True
    )

    # add-param
    subparser_add_param = subparser_mod.add_parser(
        "add-param",
        help="Add a pipeline parameter. If parameter already exists, " "it updates the value.",
    )
    subparser_add_param.add_argument("param_name", help="parameter name", metavar="PARAM-NAME")
    subparser_add_param.add_argument(
        "--default",
        dest="param_default",
        nargs="+",
        help="default value(s) for the parameter",
        metavar="DEFAULT",
    )
    subparser_add_param.add_argument(
        "-t",
        "--type",
        dest="param_type",
        help="parameter type (Default: %(default)s)",
        type=ParamType,
        choices=list(ParamType),
        default=None,
    )
    subparser_add_param.set_defaults(action=action_add_param)

    # update-param
    subparser_update_param = subparser_mod.add_parser(
        "update-param",
        help="Update an existing pipeline parameter's default value.",
    )
    subparser_update_param.add_argument("param_name", help="parameter name", metavar="PARAM-NAME")
    subparser_update_param.add_argument(
        "--default",
        dest="param_default",
        nargs="+",
        required=True,
        help="new default value(s) for the parameter",
        metavar="DEFAULT",
    )
    subparser_update_param.set_defaults(action=action_update_param)

    # remove-param
    subparser_remove_param = subparser_mod.add_parser(
        "remove-param",
        help="Remove the specified parameter from the pipeline.",
    )
    subparser_remove_param.add_argument("param_name", help="parameter name", metavar="PARAM-NAME")
    subparser_remove_param.set_defaults(action=action_remove_param)


class PipelineParamBase(PipelineFileOperation):

    def __init__(self):
        super().__init__()

    def _get_params_paths(self, kind: str) -> list[YAMLPath]:
        if kind == "Pipeline":
            return [["spec", "params"]]
        else:
            return [["spec", "pipelineSpec", "params"]]

    def _get_params_parent_paths(self, kind: str) -> list[YAMLPath]:
        if kind == "Pipeline":
            return [["spec"]]
        else:
            return [["spec", "pipelineSpec"]]

    def _find_param_index(self, params: list, param_name: str) -> int | None:
        for index, param in enumerate(params):
            if param.get("name") == param_name:
                return index
        return None

    def handle_pipeline_file(self, file_path: FilePath, loaded_doc: Any, style: YAMLStyle) -> None:
        self._handle(file_path, loaded_doc, style, "Pipeline")

    def handle_pipeline_run_file(
        self, file_path: FilePath, loaded_doc: Any, style: YAMLStyle
    ) -> None:
        self._handle(file_path, loaded_doc, style, "PipelineRun")

    def _handle(
        self,
        file_path: FilePath,
        loaded_doc: Any,
        style: YAMLStyle,
        kind: str,
    ) -> None:
        raise NotImplementedError


class AddPipelineParamOperation(PipelineParamBase):
    def __init__(
        self,
        param_name: str,
        param_default: str | List[str] | None = None,
        param_type: ParamType | None = None,
    ) -> None:
        super().__init__()
        self.param_name = param_name
        self.param_default = param_default
        self.param_type = param_type

    def _build_param_data(self) -> dict:
        data: dict[str, Any] = {"name": self.param_name}
        if self.param_type is not None:
            data["type"] = str(self.param_type)
        if self.param_default is not None:
            data["default"] = self.param_default
        return data

    def _handle(
        self,
        file_path: FilePath,
        loaded_doc: Any,
        style: YAMLStyle,
        kind: str,
    ) -> None:
        params_paths = self._get_params_paths(kind)
        parent_paths = self._get_params_parent_paths(kind)

        for params_path, parent_path in zip(params_paths, parent_paths):
            try:
                parent = loaded_doc
                for key in parent_path:
                    parent = parent[key]
            except KeyError:
                continue

            if "params" not in parent:
                new_data = {"params": [self._build_param_data()]}
                logger.info(
                    "pipeline in '%s': param '%s' will be created "
                    "(params section will be created)",
                    file_path,
                    self.param_name,
                )
                yamledit = EditYAMLEntry(file_path, style=style)
                yamledit.insert(parent_path, new_data)
                return

            params = parent["params"]
            param_index = self._find_param_index(params, self.param_name)

            if param_index is not None:
                existing_param = params[param_index]
                new_data = self._build_param_data()

                if self._param_matches(existing_param, new_data):
                    logger.info(
                        "pipeline in '%s': param '%s' already has required values",
                        file_path,
                        self.param_name,
                    )
                    return

                logger.info(
                    "pipeline in '%s': param '%s' will be updated",
                    file_path,
                    self.param_name,
                )
                path = list(params_path) + [param_index]
                yamledit = EditYAMLEntry(file_path, style=style)
                yamledit.replace(path, new_data)
                return

            logger.info(
                "pipeline in '%s': param '%s' will be created",
                file_path,
                self.param_name,
            )
            yamledit = EditYAMLEntry(file_path, style=style)
            yamledit.insert(params_path, self._build_param_data())

    def _param_matches(self, existing: dict, new: dict) -> bool:
        for key in ("name", "type", "default"):
            existing_val = existing.get(key)
            new_val = new.get(key)
            if isinstance(existing_val, list) and isinstance(new_val, list):
                if set(existing_val) != set(new_val):
                    return False
            elif existing_val != new_val:
                return False
        return True


class UpdatePipelineParamOperation(PipelineParamBase):
    def __init__(
        self,
        param_name: str,
        param_default: str | List[str],
    ) -> None:
        super().__init__()
        self.param_name = param_name
        self.param_default = param_default

    def _handle(
        self,
        file_path: FilePath,
        loaded_doc: Any,
        style: YAMLStyle,
        kind: str,
    ) -> None:
        params_paths = self._get_params_paths(kind)
        parent_paths = self._get_params_parent_paths(kind)

        for params_path, parent_path in zip(params_paths, parent_paths):
            try:
                parent = loaded_doc
                for key in parent_path:
                    parent = parent[key]
            except KeyError:
                continue

            if "params" not in parent:
                logger.warning(
                    "pipeline in '%s': no params section, nothing to update",
                    file_path,
                )
                return

            params = parent["params"]
            param_index = self._find_param_index(params, self.param_name)

            if param_index is None:
                logger.warning(
                    "pipeline in '%s': param '%s' does not exist, nothing to update",
                    file_path,
                    self.param_name,
                )
                return

            existing_param = params[param_index]
            existing_default = existing_param.get("default")

            if isinstance(existing_default, list) and isinstance(self.param_default, list):
                if set(existing_default) == set(self.param_default):
                    logger.info(
                        "pipeline in '%s': param '%s' already has required default",
                        file_path,
                        self.param_name,
                    )
                    return
            elif existing_default == self.param_default:
                logger.info(
                    "pipeline in '%s': param '%s' already has required default",
                    file_path,
                    self.param_name,
                )
                return

            new_data = dict(existing_param)
            new_data["default"] = self.param_default

            logger.info(
                "pipeline in '%s': param '%s' default will be updated",
                file_path,
                self.param_name,
            )
            path = list(params_path) + [param_index]
            yamledit = EditYAMLEntry(file_path, style=style)
            yamledit.replace(path, new_data)


class RemovePipelineParamOperation(PipelineParamBase):
    def __init__(self, param_name: str) -> None:
        super().__init__()
        self.param_name = param_name

    def _handle(
        self,
        file_path: FilePath,
        loaded_doc: Any,
        style: YAMLStyle,
        kind: str,
    ) -> None:
        params_paths = self._get_params_paths(kind)
        parent_paths = self._get_params_parent_paths(kind)

        for params_path, parent_path in zip(params_paths, parent_paths):
            try:
                parent = loaded_doc
                for key in parent_path:
                    parent = parent[key]
            except KeyError:
                continue

            if "params" not in parent:
                logger.info(
                    "pipeline in '%s': no params section, nothing to remove",
                    file_path,
                )
                return

            params = parent["params"]
            param_index = self._find_param_index(params, self.param_name)

            if param_index is None:
                logger.info(
                    "pipeline in '%s': param '%s' does not exist, nothing to remove",
                    file_path,
                    self.param_name,
                )
                return

            logger.info(
                "pipeline in '%s': param '%s' will be removed",
                file_path,
                self.param_name,
            )
            path = list(params_path) + [param_index]
            yamledit = EditYAMLEntry(file_path, style=style)
            yamledit.delete(path)


def _get_search_places(args) -> list[str]:
    search_places = [path for path in args.file_or_dir if path]
    relative_tekton_dir = Path("./.tekton")
    if not search_places and relative_tekton_dir.exists():
        search_places = [str(relative_tekton_dir.absolute())]
    return search_places


def _parse_default_value(args) -> str | list[str] | None:
    if args.param_default is None:
        return None
    if hasattr(args, "param_type") and args.param_type == ParamType.array:
        return args.param_default
    if len(args.param_default) == 1:
        return args.param_default[0]
    return args.param_default


def action_add_param(args) -> None:
    default_value = _parse_default_value(args)
    search_places = _get_search_places(args)

    op = AddPipelineParamOperation(args.param_name, default_value, args.param_type)
    for file_path in iterate_files_or_dirs(search_places):
        op.handle(str(file_path))


def action_update_param(args) -> None:
    default_value = args.param_default
    if len(default_value) == 1:
        default_value = default_value[0]

    search_places = _get_search_places(args)

    op = UpdatePipelineParamOperation(args.param_name, default_value)
    for file_path in iterate_files_or_dirs(search_places):
        op.handle(str(file_path))


def action_remove_param(args) -> None:
    search_places = _get_search_places(args)

    op = RemovePipelineParamOperation(args.param_name)
    for file_path in iterate_files_or_dirs(search_places):
        op.handle(str(file_path))
