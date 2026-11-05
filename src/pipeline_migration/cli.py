import argparse
import logging

from pipeline_migration import __version__
from pipeline_migration.actions.add_task import register_cli as register_add_task_cli
from pipeline_migration.actions.modify import register_cli as register_modify_cli
from pipeline_migration.actions.modify.generic import register_cli_v2 as register_generic_cli_v2
from pipeline_migration.actions.modify.pipeline import register_cli_v2 as register_pipeline_cli_v2
from pipeline_migration.actions.modify.task import register_cli_v2 as register_task_cli_v2
from pipeline_migration.actions.migrate.cli import register_cli as register_migrate_cli
from pipeline_migration.actions.format import register_cli as register_format_cli
from pipeline_migration.api_version import (
    ENV_API_VERSION,
    ApiVersion,
    UnsupportedApiVersion,
    get_api_version,
)

logging.basicConfig(level=logging.DEBUG, format="%(levelname)s:%(asctime)s:%(name)s:%(message)s")
logger = logging.getLogger("cli")


def build_parser(api_version: ApiVersion) -> argparse.ArgumentParser:
    """Build the CLI parser exposing the command structure of the given API version."""
    parser = argparse.ArgumentParser(
        description="Pipeline migration tool for Konflux CI.",
        epilog=f"Command structure: API version {api_version}, selected by {ENV_API_VERSION} "
        f"(supported: {', '.join(str(v) for v in ApiVersion)}).",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")
    subparser = parser.add_subparsers(title="subcommands to manage build pipelines", required=True)
    register_migrate_cli(subparser)

    if api_version == ApiVersion.V1:
        register_add_task_cli(subparser)
        register_modify_cli(subparser)
    elif api_version == ApiVersion.V2:
        register_task_cli_v2(subparser)
        register_pipeline_cli_v2(subparser)
        register_generic_cli_v2(subparser)

    register_format_cli(subparser)
    return parser


def main() -> None:
    """Parse CLI arguments and execute the requested subcommand."""
    try:
        api_version = get_api_version()
    except UnsupportedApiVersion as e:
        build_parser(ApiVersion.V1).error(str(e))
    logger.debug("Using CLI API version %s", api_version)
    args = build_parser(api_version).parse_args()
    args.action(args)


def entry_point():
    """Entry point for the pmt CLI; returns 1 on failure."""
    try:
        main()
    except Exception as e:
        logger.exception("Cannot do migration for pipeline. Reason: %r", e)
        return 1
