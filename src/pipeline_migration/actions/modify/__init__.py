import argparse
from typing import Final

from pipeline_migration.actions.modify.task import register_cli as register_mod_task_cli

# TODO
SUBCMD_DESCRIPTION: Final = """\
TODO
"""


def register_cli(subparser) -> None:
    modify_parser = subparser.add_parser(
        "modify",
        help="Update the specified Konflux task",
        description=SUBCMD_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    subparser_modify = modify_parser.add_subparsers(
        title="subcommands to manage given resources", required=True
    )
    register_mod_task_cli(subparser_modify)
