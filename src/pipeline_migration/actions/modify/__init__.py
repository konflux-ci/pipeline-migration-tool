import argparse
from typing import Final

from pipeline_migration.actions.modify.common import add_target_arguments
from pipeline_migration.actions.modify.generic import register_cli as register_mod_generic_cli
from pipeline_migration.actions.modify.task import register_cli as register_mod_task_cli
from pipeline_migration.actions.modify.pipeline import register_cli as register_mod_pipeline_cli

SUBCMD_DESCRIPTION: Final = """\
Allows to modify existing resources in Konflux pipelines/pipeline runs.
"""


def register_cli(subparser) -> None:
    """Register the modify subcommand and its sub-subcommands."""
    modify_parser = subparser.add_parser(
        "modify",
        help="Modify the specified resource",
        description=SUBCMD_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    add_target_arguments(modify_parser, "-f", "--file-or-dir")
    subparser_modify = modify_parser.add_subparsers(
        title="subcommands to manage given resources", required=True
    )
    register_mod_task_cli(subparser_modify)
    register_mod_pipeline_cli(subparser_modify)
    register_mod_generic_cli(subparser_modify)
