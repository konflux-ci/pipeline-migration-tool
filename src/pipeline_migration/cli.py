import argparse
import logging

from pipeline_migration.actions.add_task import register_cli as register_add_task_cli
from pipeline_migration.actions.modify import register_cli as register_modify_cli
from pipeline_migration.actions.migrate import register_cli as register_migrate_cli
from pipeline_migration.actions.format import register_cli as register_format_cli

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s:%(asctime)s:%(name)s:%(message)s")
logger = logging.getLogger("cli")


def main() -> None:
    parser = argparse.ArgumentParser(description="Pipeline migration tool for Konflux CI.")
    subparser = parser.add_subparsers(title="subcommands to manage build pipelines", required=True)
    register_migrate_cli(subparser)
    register_add_task_cli(subparser)
    register_modify_cli(subparser)
    register_format_cli(subparser)
    args = parser.parse_args()
    args.action(args)


def entry_point():
    try:
        main()
    except Exception as e:
        logger.exception("Cannot do migration for pipeline. Reason: %r", e)
        return 1
