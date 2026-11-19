import logging
import re
from typing import Any, Final

logger = logging.getLogger("migrate")


ANNOTATION_HAS_MIGRATION: Final[str] = "dev.konflux-ci.task.has-migration"
ANNOTATION_IS_MIGRATION: Final[str] = "dev.konflux-ci.task.is-migration"
ANNOTATION_PREVIOUS_MIGRATION_BUNDLE: Final[str] = "dev.konflux-ci.task.previous-migration-bundle"

ANNOTATION_TRUTH_VALUE: Final = "true"

# Example:  0.1-18a61693389c6c912df587f31bc3b4cc53eb0d5b
TASK_TAG_REGEXP: Final = r"^[0-9.]+-[0-9a-f]+$"

SCHEMA_UPGRADE: Final[dict[str, Any]] = {
    "$schema": "https://json-schema.org/draft/2020-12",
    "title": "Schema for Renovate upgrade data",
    "type": "object",
    "properties": {
        "depName": {"type": "string", "minLength": 1},
        "currentValue": {
            "type": "string",
            "minLength": 1,
            "pattern": r"^[0-9]+\.[0-9]+(\.[0-9]+)?$",
        },
        "currentDigest": {"type": "string", "pattern": "^sha256:[0-9a-f]+$"},
        "newValue": {
            "type": "string",
            "minLength": 1,
            "pattern": r"^[0-9]+\.[0-9]+(\.[0-9]+)?$",
        },
        "newDigest": {"type": "string", "pattern": "^sha256:[0-9a-f]+$"},
        "depTypes": {
            "type": "array",
            "items": {"const": "tekton-bundle"},
            "minItems": 1,
            "maxItems": 1,
        },
        "packageFile": {"type": "string", "minLength": 1},
        "parentDir": {"type": "string", "minLength": 1},
    },
    "additionalProperties": True,
    "required": [
        "currentDigest",
        "currentValue",
        "depName",
        "depTypes",
        "newDigest",
        "newValue",
        "packageFile",
        "parentDir",
    ],
}

MIGRATION_IMAGE_TAG_REGEX: Final = re.compile(
    "^"
    r"(?P<prefix>migration)-"
    r"(?P<version>\d+\.\d+(\.\d+)?)-"
    r"(?P<checksum>[0-9a-f]{64})-"
    r"(?P<timestamp>\d+)"
    "$"
)

MIGRATION_IMAGE_TAG_LIKE_PATTERN: Final = r"migration-%.%-%-%"

# Match pipeline-migration-tool CLI commands modifying pipelines with minimal diffs, i.e. through
# the yamleditor module instead of regenerating the whole document (e.g. by "yq -i").
# Line continuation is matched by [\s\\]+
# Command name can be either pipeline-migration-tool or pmt.
# API v1 matches only "modify". API v2 matches "task", "pipeline" or "generic", optionally
# preceded by environment variable assignments, e.g. PMT_API_VERSION=2 pmt task ...
REGEX_PMT_MODIFY_USAGE = re.compile(
    r"^\s*(?:"
    r"(?:pipeline-migration-tool|pmt)[\s\\]+modify"
    r"|(?:\w+=\S*\s+)*(?:pipeline-migration-tool|pmt)[\s\\]+(?:task|pipeline|generic)"
    r")\s",
    re.MULTILINE,
)

# Match the API version a migration script declares, e.g. at the top of the script:
#   export PMT_API_VERSION=2
# or as a prefix of a pmt command:
#   PMT_API_VERSION=2 pmt task ...
# The value must be a literal number, optionally quoted.
REGEX_PMT_API_VERSION = re.compile(
    r"^\s*(?:export\s+|env\s+)?(?:\w+=\S*\s+)*PMT_API_VERSION=[\"']?(\d+)[\"']?(?=[\s;]|$)",
    re.MULTILINE,
)
