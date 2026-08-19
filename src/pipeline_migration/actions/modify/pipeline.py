from abc import abstractmethod
import argparse
from enum import Enum
import json
import logging
from typing import Any, Final

from ruamel.yaml.scalarstring import LiteralScalarString

from pipeline_migration.yamleditor import EditYAMLEntry
from pipeline_migration.types import FilePath
from pipeline_migration.utils import YAMLStyle, load_yaml
from pipeline_migration.pipeline import PipelineFileOperation
from pipeline_migration.actions.modify.common import ParamType, get_nested, run_modify

logger = logging.getLogger("modify.pipeline")


SUBCMD_DESCRIPTION: Final = """\
The following are several examples for modifying pipeline parameters and results:

* Add a pipeline parameter:

    pmt modify pipeline add-param --default "" --description "Git repository URL" git-url

* Add an array parameter with default values:

    pmt modify pipeline add-param --type array --default '["val1","val2"]' my-param

* Add a parameter with an empty array default:

    pmt modify pipeline add-param --type array --default "" my-param

* Add a parameter with a multiline description:

    pmt modify pipeline add-param --default "" \\
        --description $'First line\\nSecond line' my-param

  Or using a variable:

    description=$(cat <<'EOF'
    This is a longer description
    that spans multiple lines.
    EOF
    )
    pmt modify pipeline add-param --default "" --description "$description" my-param

* Remove a pipeline parameter:

    pmt modify pipeline remove-param git-url

* Add a pipeline result:

    pmt modify pipeline add-result \\
        --description "Image digest" \\
        'IMAGE_DIGEST=$(tasks.build.results.IMAGE_DIGEST)'

* Add an array result (value is a JSON array):

    pmt modify pipeline add-result --type array \\
        'IMAGES=["$(tasks.foo.results.bar)","$(tasks.spam.results.egg)"]'

* Add an object result (value is a JSON object):

    pmt modify pipeline add-result --type object \\
        'BUILD_OUTPUT={"image_url":"$(tasks.build.results.IMAGE_URL)"}'

* Remove a pipeline result:

    pmt modify pipeline remove-result IMAGE_DIGEST

* Supported pipeline modifications:
   - add-param: adds a new parameter to the pipeline
   - remove-param: removes a parameter from the pipeline
   - add-result: adds a new result to the pipeline
   - remove-result: removes a result from the pipeline
"""


class ResultType(Enum):
    """Enum for pipeline result types: string, array or object."""

    string = "string"
    array = "array"
    object = "object"

    def __str__(self) -> str:
        return self.value


def _format_description(description: str) -> str | LiteralScalarString:
    """Format description, using YAML literal block scalar for multiline text."""
    if "\n" in description:
        if not description.endswith("\n"):
            description += "\n"
        return LiteralScalarString(description)
    return description


def _name_value_pair(arg: str) -> tuple[str, str]:
    """Parse a name=value CLI argument."""
    if "=" not in arg:
        raise argparse.ArgumentTypeError(f"Expected name=value format, got: {arg}")
    name, _, value = arg.partition("=")
    if not name:
        raise argparse.ArgumentTypeError(f"Result name must not be empty in: {arg}")
    return name, value


def _remove_from_section(
    item_name: str,
    section_key: str,
    path_prefix: list[str],
    pipeline_file: FilePath,
    style: YAMLStyle,
    loaded_doc: Any = None,
) -> None:
    doc = loaded_doc if loaded_doc is not None else load_yaml(pipeline_file, style)
    try:
        spec = get_nested(doc, path_prefix)
    except KeyError:
        return

    if section_key not in spec:
        logger.info(
            "pipeline %s '%s' does not exist in '%s', nothing to remove",
            section_key.rstrip("s"),
            item_name,
            pipeline_file,
        )
        return

    for index, item in enumerate(spec[section_key]):
        if item.get("name") == item_name:
            yamledit = EditYAMLEntry(pipeline_file, style=style)
            yamledit.delete(list(path_prefix) + [section_key, index])
            logger.info(
                "pipeline %s '%s' removed from '%s'",
                section_key.rstrip("s"),
                item_name,
                pipeline_file,
            )
            return

    logger.info(
        "pipeline %s '%s' does not exist in '%s', nothing to remove",
        section_key.rstrip("s"),
        item_name,
        pipeline_file,
    )


class PipelineBase(PipelineFileOperation):
    """Base class for pipeline-level modifications (params and results)."""

    @abstractmethod
    def _do_action(
        self,
        path_prefix: list[str],
        pipeline_file: FilePath,
        loaded_doc: Any,
        style: YAMLStyle,
    ) -> None:
        raise NotImplementedError

    def handle_pipeline_file(self, file_path: FilePath, loaded_doc: Any, style: YAMLStyle) -> None:
        self._do_action(["spec"], file_path, loaded_doc, style)

    def handle_pipeline_run_file(
        self, file_path: FilePath, loaded_doc: Any, style: YAMLStyle
    ) -> None:
        self._do_action(["spec", "pipelineSpec"], file_path, loaded_doc, style)


class PipelineAddParamOperation(PipelineBase):
    """Operation that adds a parameter to a pipeline."""

    def __init__(
        self,
        param_name: str,
        param_type: ParamType,
        description: str | LiteralScalarString,
        default: str | list[str],
    ) -> None:
        super().__init__()
        self.param_name = param_name
        self.param_type = param_type
        self.description = description
        self.default = default

    def _build_param(self) -> dict:
        param: dict[str, Any] = {
            "name": self.param_name,
            "type": str(self.param_type),
        }
        if self.description:
            param["description"] = self.description
        param["default"] = self.default
        return param

    def _do_action(
        self,
        path_prefix: list[str],
        pipeline_file: FilePath,
        loaded_doc: Any,
        style: YAMLStyle,
    ) -> None:
        try:
            spec = get_nested(loaded_doc, path_prefix)
        except KeyError:
            logger.warning("path %s does not exist in '%s'", path_prefix, pipeline_file)
            return

        if "params" not in spec:
            yamledit = EditYAMLEntry(pipeline_file, style=style)
            yamledit.insert(list(path_prefix), {"params": [self._build_param()]})
            logger.info(
                "pipeline param '%s' created (params section created) in '%s'",
                self.param_name,
                pipeline_file,
            )
            return

        for param in spec["params"]:
            if param.get("name") == self.param_name:
                logger.info(
                    "pipeline param '%s' already exists in '%s', skipping",
                    self.param_name,
                    pipeline_file,
                )
                return

        yamledit = EditYAMLEntry(pipeline_file, style=style)
        yamledit.insert(list(path_prefix) + ["params"], self._build_param())
        logger.info(
            "pipeline param '%s' created in '%s'",
            self.param_name,
            pipeline_file,
        )


class PipelineRemoveParamOperation(PipelineBase):
    """Operation that removes a parameter from a pipeline."""

    def __init__(self, param_name: str) -> None:
        super().__init__()
        self.param_name = param_name

    def handle_pipeline_run_file(
        self, file_path: FilePath, loaded_doc: Any, style: YAMLStyle
    ) -> None:
        self._do_action(["spec", "pipelineSpec"], file_path, loaded_doc, style)
        # File was modified, pass loaded_doc=None to reload the file
        _remove_from_section(self.param_name, "params", ["spec"], file_path, style, loaded_doc=None)

    def _do_action(
        self,
        path_prefix: list[str],
        pipeline_file: FilePath,
        loaded_doc: Any,
        style: YAMLStyle,
    ) -> None:
        _remove_from_section(
            self.param_name, "params", path_prefix, pipeline_file, style, loaded_doc
        )


class PipelineAddResultOperation(PipelineBase):
    """Operation that adds a result to a pipeline."""

    def __init__(
        self,
        name: str,
        value: str | list[str] | dict[str, Any],
        result_type: ResultType,
        description: str | LiteralScalarString,
    ) -> None:
        super().__init__()
        self.name = name
        self.value = value
        self.result_type = result_type
        self.description = description

    def _build_result(self) -> dict:
        result: dict[str, Any] = {
            "name": self.name,
            "type": str(self.result_type),
        }
        if self.description:
            result["description"] = self.description
        result["value"] = self.value
        return result

    def _do_action(
        self,
        path_prefix: list[str],
        pipeline_file: FilePath,
        loaded_doc: Any,
        style: YAMLStyle,
    ) -> None:
        try:
            spec = get_nested(loaded_doc, path_prefix)
        except KeyError:
            logger.warning("path %s does not exist in '%s'", path_prefix, pipeline_file)
            return

        if "results" not in spec:
            yamledit = EditYAMLEntry(pipeline_file, style=style)
            yamledit.insert(list(path_prefix), {"results": [self._build_result()]})
            logger.info(
                "pipeline result '%s' created (results section created) in '%s'",
                self.name,
                pipeline_file,
            )
            return

        for result in spec["results"]:
            if result.get("name") == self.name:
                existing_value = result.get("value")
                if existing_value != self.value:
                    logger.warning(
                        "pipeline result '%s' already exists in '%s' with a different value "
                        "(existing: '%s', requested: '%s'), skipping",
                        self.name,
                        pipeline_file,
                        existing_value,
                        self.value,
                    )
                else:
                    logger.info(
                        "pipeline result '%s' already exists in '%s', skipping",
                        self.name,
                        pipeline_file,
                    )
                return

        yamledit = EditYAMLEntry(pipeline_file, style=style)
        yamledit.insert(list(path_prefix) + ["results"], self._build_result())
        logger.info(
            "pipeline result '%s' created in '%s'",
            self.name,
            pipeline_file,
        )


class PipelineRemoveResultOperation(PipelineBase):
    """Operation that removes a result from a pipeline."""

    def __init__(self, result_name: str) -> None:
        super().__init__()
        self.result_name = result_name

    def _do_action(
        self,
        path_prefix: list[str],
        pipeline_file: FilePath,
        loaded_doc: Any,
        style: YAMLStyle,
    ) -> None:
        _remove_from_section(
            self.result_name, "results", path_prefix, pipeline_file, style, loaded_doc
        )


def register_cli(subparser) -> None:
    """Register the 'pipeline' subcommand and its sub-actions on the CLI parser."""
    mod_pipeline_parser = subparser.add_parser(
        "pipeline",
        help="Update pipeline-level parameters and results",
        description=SUBCMD_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparser_mod = mod_pipeline_parser.add_subparsers(
        title="subcommands to modify pipeline", required=True
    )

    # add-param
    subparser_add_param = subparser_mod.add_parser(
        "add-param",
        help="Add a parameter to the pipeline. If the parameter already exists, this is a no-op.",
    )
    subparser_add_param.add_argument("param_name", help="parameter name", metavar="NAME")
    subparser_add_param.add_argument(
        "-t",
        "--type",
        dest="param_type",
        help="parameter type (Default: %(default)s)",
        type=ParamType,
        choices=list(ParamType),
        default=ParamType.string,
    )
    subparser_add_param.add_argument(
        "--description",
        dest="description",
        default="",
        help="parameter description (Default: empty string). "
        "Multiline descriptions are added as YAML literal strings.",
    )
    subparser_add_param.add_argument(
        "--default",
        dest="default",
        required=True,
        help="parameter default value. Required because the tool cannot supply param values "
        "to PipelineRun resources. A param with a default is never 'required' in Tekton, "
        "so no PipelineRun breaks from a missing value. "
        'For array type, specify elements as a JSON array (e.g. \'["val1","val2"]\'). '
        'An empty string "" is interpreted as an empty array.',
    )
    subparser_add_param.set_defaults(action=action_add_param)

    # remove-param
    subparser_remove_param = subparser_mod.add_parser(
        "remove-param",
        help="Remove the specified parameter from the pipeline.",
    )
    subparser_remove_param.add_argument(
        "param_name",
        help="parameter name to remove",
        metavar="NAME",
    )
    subparser_remove_param.set_defaults(action=action_remove_param)

    # add-result
    subparser_add_result = subparser_mod.add_parser(
        "add-result",
        help="Add a result to the pipeline. If the result already exists, this is a no-op.",
    )
    subparser_add_result.add_argument(
        "name_value_pair",
        type=_name_value_pair,
        help="result name=value pair",
        metavar="NAME=VALUE",
    )
    subparser_add_result.add_argument(
        "-t",
        "--type",
        dest="result_type",
        help="result type (Default: %(default)s)",
        type=ResultType,
        choices=list(ResultType),
        default=ResultType.string,
    )
    subparser_add_result.add_argument(
        "--description",
        dest="description",
        default="",
        help="result description (Default: empty string). "
        "Multiline descriptions are added as YAML literal strings.",
    )
    subparser_add_result.set_defaults(action=action_add_result)

    # remove-result
    subparser_remove_result = subparser_mod.add_parser(
        "remove-result",
        help="Remove the specified result from the pipeline.",
    )
    subparser_remove_result.add_argument(
        "result_name",
        help="result name to remove",
        metavar="NAME",
    )
    subparser_remove_result.set_defaults(action=action_remove_result)


def action_add_param(args) -> None:
    """CLI action handler to add a parameter to the pipeline."""
    description = _format_description(args.description)

    if args.param_type == ParamType.array:
        if args.default == "":
            default: str | list[str] = []
        else:
            try:
                default = json.loads(args.default)
            except json.JSONDecodeError:
                raise SystemExit(
                    f"error: --default for array type must be a JSON array, got: {args.default}"
                )
            if not isinstance(default, list):
                raise SystemExit(
                    f"error: --default for array type must be a JSON array, got: {args.default}"
                )
    else:
        default = args.default

    op = PipelineAddParamOperation(args.param_name, args.param_type, description, default)
    run_modify(op, args)


def action_remove_param(args) -> None:
    """CLI action handler to remove a parameter from the pipeline."""
    op = PipelineRemoveParamOperation(args.param_name)
    run_modify(op, args)


def action_add_result(args) -> None:
    """CLI action handler to add a result to the pipeline."""
    description = _format_description(args.description)
    name, raw_value = args.name_value_pair

    try:
        value = json.loads(raw_value)
        if not isinstance(value, (list, dict)):
            value = raw_value
    except (json.JSONDecodeError, TypeError):
        value = raw_value

    op = PipelineAddResultOperation(name, value, args.result_type, description)
    run_modify(op, args)


def action_remove_result(args) -> None:
    """CLI action handler to remove a result from the pipeline."""
    op = PipelineRemoveResultOperation(args.result_name)
    run_modify(op, args)
