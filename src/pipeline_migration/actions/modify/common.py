import logging
from pathlib import Path
from enum import Enum
from typing import Any

from pipeline_migration.actions.modify.dry_run import dry_run
from pipeline_migration.pipeline import iterate_files_or_dirs

logger = logging.getLogger("modify")


class ParamType(Enum):
    """Enum for parameter types: string or array."""

    string = "string"
    array = "array"

    def __str__(self) -> str:
        return self.value


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
