import logging
from pathlib import Path

from pipeline_migration.actions.modify.dry_run import dry_run
from pipeline_migration.pipeline import iterate_files_or_dirs

logger = logging.getLogger("modify")


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
