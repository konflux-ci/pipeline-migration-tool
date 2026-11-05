import os
from collections.abc import Mapping
from enum import IntEnum
from typing import Final

ENV_API_VERSION: Final = "PMT_API_VERSION"


class ApiVersion(IntEnum):
    """Supported versions of the pmt command structure."""

    V1 = 1
    V2 = 2

    def __str__(self) -> str:
        return str(self.value)


DEFAULT_API_VERSION: Final = ApiVersion.V1

# API version of migration scripts that do not choose one. It is pinned independently of
# DEFAULT_API_VERSION, so changing the default for interactive use never breaks released scripts.
MIGRATION_API_VERSION: Final = ApiVersion.V1


class UnsupportedApiVersion(ValueError):
    """The requested API version is not supported by this pmt release."""


def get_api_version(environ: Mapping[str, str] = os.environ) -> ApiVersion:
    """Return the API version requested via the environment, or the default one.

    :raises UnsupportedApiVersion: if the variable is set to an unknown version.
    """
    value = environ.get(ENV_API_VERSION, "").strip()
    if not value:
        return DEFAULT_API_VERSION
    try:
        return ApiVersion(int(value))
    except ValueError:
        supported = ", ".join(str(v) for v in ApiVersion)
        raise UnsupportedApiVersion(
            f"{ENV_API_VERSION}={value!r} is not supported by this pmt release. "
            f"Supported API versions: {supported}."
        ) from None
