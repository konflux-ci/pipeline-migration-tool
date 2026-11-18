import pytest

from pipeline_migration.api_version import (
    ENV_API_VERSION,
    ApiVersion,
    UnsupportedApiVersion,
    get_api_version,
)


@pytest.mark.parametrize(
    "environ,expected",
    [
        pytest.param({}, ApiVersion.V1, id="unset-defaults-to-v1"),
        pytest.param({ENV_API_VERSION: ""}, ApiVersion.V1, id="empty-defaults-to-v1"),
        pytest.param({ENV_API_VERSION: "1"}, ApiVersion.V1, id="explicit-v1"),
        pytest.param({ENV_API_VERSION: "2"}, ApiVersion.V2, id="explicit-v2"),
        pytest.param({ENV_API_VERSION: " 2\n"}, ApiVersion.V2, id="surrounding-whitespace"),
    ],
)
def test_get_api_version(environ, expected):
    assert get_api_version(environ) == expected


@pytest.mark.parametrize("value", ["0", "3", "v2", "2.0", "latest"])
def test_reject_unsupported_api_version(value):
    with pytest.raises(UnsupportedApiVersion, match=f"{ENV_API_VERSION}='{value}'.*: 1, 2"):
        get_api_version({ENV_API_VERSION: value})


def test_read_process_environment_by_default(monkeypatch):
    monkeypatch.setenv(ENV_API_VERSION, "2")
    assert get_api_version() == ApiVersion.V2
    monkeypatch.delenv(ENV_API_VERSION)
    assert get_api_version() == ApiVersion.V1
