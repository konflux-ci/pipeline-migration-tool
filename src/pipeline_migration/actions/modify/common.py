import argparse
import logging
import re
from pathlib import Path
from enum import Enum
from typing import Any

from pipeline_migration.actions.modify.dry_run import dry_run
from pipeline_migration.api_version import ApiVersion
from pipeline_migration.pipeline import iterate_files_or_dirs

logger = logging.getLogger("modify")


class ParamType(Enum):
    """Enum for parameter types: string or array."""

    string = "string"
    array = "array"

    def __str__(self) -> str:
        return self.value


FILE_OR_DIR_HELP = (
    "Specify locations from where finding out pipelines. "
    "A pipeline can be included in a PipelineRun or a single Pipeline definition. "
    "%(prog)s searches pipelines from given locations by rules, if files are specified, "
    "search just pipelines from them. If directories are specified, search YAML files from the "
    "first level of each one. If neither is specified, the location defaults to ./.tekton/ "
    "directory."
)


# Placeholder of the command prefix in subcommand descriptions, with optional resource options:
# {{pmt}} or {{pmt -f FILE --dry-run}}
_COMMAND_PLACEHOLDER = re.compile(r"\{\{pmt(?P<options>[^}]*)\}\}")


def command_prefix(resource: str, api_version: ApiVersion, options: str = "") -> str:
    """Return the command selecting the resource in the given API version, e.g. 'pmt task'.

    Resource options (-f, --dry-run) belong to "modify" in API v1 and to the resource in API v2.
    """
    match api_version:
        case ApiVersion.V1:
            words = ["pmt modify", options, resource]
        case ApiVersion.V2:
            words = ["pmt", resource, options]
    return " ".join(word for word in words if word)


def render_description(template: str, resource: str, api_version: ApiVersion) -> str:
    """Render a subcommand description shared by all API versions.

    Each ``{{pmt OPTIONS}}`` placeholder is replaced by the command prefix of the API version, so
    the examples are written once for all of them.
    """
    return _COMMAND_PLACEHOLDER.sub(
        lambda m: command_prefix(resource, api_version, m["options"].strip()), template
    )


def add_target_arguments(
    parser: argparse.ArgumentParser, *file_flags: str, metavar: str | None = None
) -> None:
    """Add the options selecting which pipeline files to modify and how.

    Both API versions store the locations in ``file_or_dir``, so the operations do not depend on
    the spelling of the option.

    :param file_flags: option strings of the locations option, e.g. ``"-f", "--file"``.
    :param metavar: name of the option value in help messages.
    """
    parser.add_argument(
        *file_flags,
        dest="file_or_dir",
        metavar=metavar,
        action="append",
        default=[],
        help=FILE_OR_DIR_HELP,
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Show a unified diff of the changes that would be made.",
    )


def run_modify(op, args, skip_on=()) -> None:
    """Apply op to each pipeline file, or print a dry-run diff."""
    search_places = [path for path in args.file_or_dir if path]
    relative_tekton_dir = Path("./.tekton")
    if not search_places and relative_tekton_dir.exists():
        search_places = [str(relative_tekton_dir.absolute())]

    for file_path in iterate_files_or_dirs(search_places):
        try:
            if args.dry_run:
                dry_run(file_path, op.handle)
            else:
                op.handle(str(file_path))
        except Exception as e:
            if skip_on and isinstance(e, skip_on):
                logger.warning("Skipped file %s update: %s", file_path, e)
            else:
                raise


def get_nested(doc: Any, path: list) -> Any:
    """Traverse a nested mapping along path, raising KeyError if any key is missing."""
    for p in path:
        doc = doc[p]
    return doc
