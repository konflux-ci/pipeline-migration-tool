import argparse
import shutil
from pathlib import Path

import pytest
import responses

from pipeline_migration.api_version import ENV_API_VERSION, ApiVersion
from pipeline_migration.actions.modify.task import subcmd_description
from pipeline_migration.cli import build_parser, entry_point
from tests.actions.test_add_task_cli import (
    BUNDLE_REF,
    TASK_NAME,
    TEST_TASK_VALUES,
    VerifyUpdatedPipeline,
    mock_get_bundle_image_manifest,
    mock_get_digest_for_specific_tag,
)


def subcommands(parser: argparse.ArgumentParser) -> set[str]:
    actions = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    return set(actions[0].choices)


def run_pmt(monkeypatch, api_version: str | None, *args: str) -> None:
    if api_version is None:
        monkeypatch.delenv(ENV_API_VERSION, raising=False)
    else:
        monkeypatch.setenv(ENV_API_VERSION, api_version)
    monkeypatch.setattr("sys.argv", ["pmt", *args])
    assert entry_point() is None, "pmt command failed"


@pytest.mark.parametrize(
    "api_version,expected",
    [
        (ApiVersion.V1, {"migrate", "add-task", "modify", "format"}),
        (ApiVersion.V2, {"migrate", "task", "pipeline", "generic", "format"}),
    ],
)
def test_subcommands_of_api_version(api_version, expected):
    assert subcommands(build_parser(api_version)) == expected


def test_default_to_api_v1(monkeypatch, capsys):
    monkeypatch.delenv(ENV_API_VERSION, raising=False)
    monkeypatch.setattr("sys.argv", ["pmt", "--help"])
    with pytest.raises(SystemExit):
        entry_point()
    out = capsys.readouterr().out
    assert "{migrate,add-task,modify,format}" in out
    assert "API version 1" in out


def test_reject_unsupported_api_version(monkeypatch, capsys):
    monkeypatch.setenv(ENV_API_VERSION, "3")
    monkeypatch.setattr("sys.argv", ["pmt", "format"])
    with pytest.raises(SystemExit) as exc_info:
        entry_point()
    assert exc_info.value.code == 2
    assert "PMT_API_VERSION='3' is not supported" in capsys.readouterr().err


@pytest.mark.parametrize(
    "api_version,args",
    [
        pytest.param("1", ["task", "clone", "add-param", "p", "v"], id="v1-has-no-task"),
        pytest.param("1", ["pipeline", "remove-param", "p"], id="v1-has-no-pipeline"),
        pytest.param("2", ["modify", "task", "clone", "add-param", "p", "v"], id="v2-no-modify"),
        pytest.param("2", ["add-task", BUNDLE_REF], id="v2-has-no-add-task"),
        pytest.param("2", ["task", "clone", "matrix-add-param", "p", "v"], id="v2-renamed-op"),
    ],
)
def test_commands_unavailable_in_other_api_version(api_version, args, monkeypatch):
    monkeypatch.setenv(ENV_API_VERSION, api_version)
    monkeypatch.setattr("sys.argv", ["pmt", *args])
    with pytest.raises(SystemExit) as exc_info:
        entry_point()
    assert exc_info.value.code == 2


class TestTaskTargetingV2:
    """API v2 'pmt task' accepts an optional TASK-NAME before the operation"""

    @pytest.fixture
    def parser(self) -> argparse.ArgumentParser:
        return build_parser(ApiVersion.V2)

    def test_parse_task_name_and_operation(self, parser):
        args = parser.parse_args(
            ["task", "-f", "a.yaml", "--dry-run", "clone", "add-param", "-t", "array", "p", "v"]
        )
        assert args.task_name == "clone"
        assert args.file_or_dir == ["a.yaml"]
        assert args.dry_run
        assert args.param_name == "p"
        assert args.param_value == ["v"]

    def test_parse_add_without_task_name(self, parser, monkeypatch):
        monkeypatch.setattr(
            "pipeline_migration.actions.add_task.validate_bundle_ref", lambda value: value
        )
        args = parser.parse_args(["task", "-f", "a.yaml", "add", BUNDLE_REF, "--finally"])
        assert args.task_name is None
        assert args.bundle_ref == BUNDLE_REF
        assert args.add_to_finally
        assert args.file_or_dir == ["a.yaml"]

    @pytest.mark.parametrize(
        "args,error",
        [
            (["task", "add-param", "p", "v"], "operation 'add-param' requires TASK-NAME"),
            (["task", "clone", "add", BUNDLE_REF], "operation 'add' does not accept TASK-NAME"),
            (["task", "clone"], "missing an operation for task 'clone'"),
            (["task", "clone", "unknown-op"], "no operation found in 'clone unknown-op'"),
            (["task", "add-parm", "p", "v"], "no operation found in 'add-parm p'"),
            (["task", "clone", "-f", "x.yaml", "add-param", "p", "v"], "option '-f' must precede"),
            (["task", "clone", "--dry-run", "add-param", "p", "v"], "option '--dry-run' must"),
            (["task"], "required"),
        ],
    )
    def test_reject_invalid_targeting(self, parser, args, error, capsys):
        with pytest.raises(SystemExit) as exc_info:
            parser.parse_args(args)
        assert exc_info.value.code == 2
        assert error in capsys.readouterr().err

    def test_list_operations_in_unknown_operation_error(self, parser, capsys):
        with pytest.raises(SystemExit):
            parser.parse_args(["task", "clone", "unknown-op"])
        assert "add, add-param, remove-param, add-matrix-param" in capsys.readouterr().err


class TestArgparseInternals:
    """Pin the argparse internals _TaskOperationsAction relies on.

    The action subclasses the private argparse._SubParsersAction. If any of these fail after a
    Python upgrade, the TASK-NAME/operation dispatching must be revisited.
    """

    @pytest.fixture
    def operations_action(self) -> argparse._SubParsersAction:
        task_parser = build_parser(ApiVersion.V2)._subparsers._group_actions[0].choices["task"]
        actions = [a for a in task_parser._actions if isinstance(a, argparse._SubParsersAction)]
        return actions[0]

    def test_subparsers_action_keeps_name_parser_map(self, operations_action):
        assert "add" in operations_action._name_parser_map
        assert "add-param" in operations_action._name_parser_map

    def test_choices_accept_any_word(self, operations_action):
        # argparse validates the first word against choices before calling the action
        assert "any-task-name" in operations_action.choices
        assert list(operations_action.choices) == list(operations_action._name_parser_map)

    def test_parser_action_receives_all_remaining_words(self, operations_action):
        assert operations_action.nargs == argparse.PARSER

    def test_help_lists_operations(self, capsys):
        with pytest.raises(SystemExit):
            build_parser(ApiVersion.V2).parse_args(["task", "--help"])
        out = capsys.readouterr().out
        assert "[TASK-NAME] OPERATION" in out
        for operation in ("add", "add-param", "add-matrix-param", "set-bundle"):
            assert operation in out


# Not hosted on quay.io, so the reference is not resolved by the registry
NEW_BUNDLE = f"registry.example.com/org/task-git-clone:0.2@sha256:{'a' * 64}"

ADD_TASK_PARAM = ["modify", "-f", "FILE", "task", "clone", "add-param", "url", "https://x"]
ADD_MATRIX_PARAM = ["modify", "-f", "FILE", "task", "clone", "matrix-add-param", "p", "a"]
ADD_RESULT = ["modify", "-f", "FILE", "pipeline", "add-result", "URL=$(tasks.clone.results.url)"]

# Equivalent commands in API v1 and API v2, preceded by an optional API v1 setup command applied
# to the pipeline before. FILE is replaced by the pipeline file path.
EQUIVALENT_COMMANDS = [
    pytest.param(
        None,
        ["modify", "-f", "FILE", "task", "clone", "add-param", "new-param", "value"],
        ["task", "-f", "FILE", "clone", "add-param", "new-param", "value"],
        id="task-add-param",
    ),
    pytest.param(
        None,
        ["modify", "-f", "FILE", "task", "clone", "add-param", "-t", "array", "p", "v1", "v2"],
        ["task", "-f", "FILE", "clone", "add-param", "-t", "array", "p", "v1", "v2"],
        id="task-add-param-array",
    ),
    pytest.param(
        ADD_TASK_PARAM,
        ["modify", "-f", "FILE", "task", "clone", "remove-param", "url"],
        ["task", "-f", "FILE", "clone", "remove-param", "url"],
        id="task-remove-param",
    ),
    pytest.param(
        None,
        ["modify", "-f", "FILE", "task", "clone", "matrix-add-param", "-t", "array", "p", "a"],
        ["task", "-f", "FILE", "clone", "add-matrix-param", "-t", "array", "p", "a"],
        id="task-add-matrix-param",
    ),
    pytest.param(
        ADD_MATRIX_PARAM,
        ["modify", "-f", "FILE", "task", "clone", "matrix-remove-param", "p"],
        ["task", "-f", "FILE", "clone", "remove-matrix-param", "p"],
        id="task-remove-matrix-param",
    ),
    pytest.param(
        None,
        ["modify", "-f", "FILE", "task", "clone", "rename", "fetch", "-r", "git-fetch"],
        ["task", "-f", "FILE", "clone", "rename", "fetch", "-r", "git-fetch"],
        id="task-rename",
    ),
    pytest.param(
        None,
        ["modify", "-f", "FILE", "task", "clone", "set-bundle", NEW_BUNDLE],
        ["task", "-f", "FILE", "clone", "set-bundle", NEW_BUNDLE],
        id="task-set-bundle",
    ),
    pytest.param(
        None,
        ["modify", "-f", "FILE", "task", "clone", "set-bundle", NEW_BUNDLE, "-r", "git-clone"],
        ["task", "-f", "FILE", "clone", "set-bundle", NEW_BUNDLE, "-r", "git-clone"],
        id="task-set-bundle-task-ref-name",
    ),
    pytest.param(
        None,
        ["modify", "-f", "FILE", "pipeline", "add-param", "--default", "", "new-param"],
        ["pipeline", "-f", "FILE", "add-param", "--default", "", "new-param"],
        id="pipeline-add-param",
    ),
    pytest.param(
        None,
        ["modify", "-f", "FILE", "pipeline", "remove-param", "revision"],
        ["pipeline", "-f", "FILE", "remove-param", "revision"],
        id="pipeline-remove-param",
    ),
    pytest.param(
        None,
        ["modify", "-f", "FILE", "pipeline", "add-result", "URL=$(tasks.clone.results.url)"],
        ["pipeline", "-f", "FILE", "add-result", "URL=$(tasks.clone.results.url)"],
        id="pipeline-add-result",
    ),
    pytest.param(
        ADD_RESULT,
        ["modify", "-f", "FILE", "pipeline", "remove-result", "URL"],
        ["pipeline", "-f", "FILE", "remove-result", "URL"],
        id="pipeline-remove-result",
    ),
    pytest.param(
        None,
        ["modify", "-f", "FILE", "generic", "insert", '["metadata"]', '{"labels": {"a": "b"}}'],
        ["generic", "-f", "FILE", "insert", '["metadata"]', '{"labels": {"a": "b"}}'],
        id="generic-insert",
    ),
    pytest.param(
        None,
        ["modify", "-f", "FILE", "generic", "replace", '["metadata"]', '{"name": "new"}'],
        ["generic", "-f", "FILE", "replace", '["metadata"]', '{"name": "new"}'],
        id="generic-replace",
    ),
    pytest.param(
        None,
        ["modify", "-f", "FILE", "generic", "remove", '["metadata"]'],
        ["generic", "-f", "FILE", "remove", '["metadata"]'],
        id="generic-remove",
    ),
]


@pytest.mark.parametrize("setup_args,v1_args,v2_args", EQUIVALENT_COMMANDS)
def test_v1_and_v2_commands_produce_identical_results(
    setup_args, v1_args, v2_args, pipeline_and_run_yaml, tmp_path, monkeypatch
):
    def with_file(args: list[str], file_path: Path) -> list[str]:
        return [str(file_path) if arg == "FILE" else arg for arg in args]

    v1_file = tmp_path / "v1.yaml"
    v1_file.write_text(pipeline_and_run_yaml)
    if setup_args:
        run_pmt(monkeypatch, None, *with_file(setup_args, v1_file))
    v2_file = tmp_path / "v2.yaml"
    shutil.copyfile(v1_file, v2_file)
    origin_content = v1_file.read_text()

    run_pmt(monkeypatch, None, *with_file(v1_args, v1_file))
    run_pmt(monkeypatch, "2", *with_file(v2_args, v2_file))

    assert v1_file.read_text() != origin_content, "the command is expected to modify the file"
    assert v2_file.read_text() == v1_file.read_text()


@pytest.mark.parametrize(
    "resource_args",
    [
        ["task", "clone", "add-param", "new-param", "value"],
        ["pipeline", "add-param", "--default", "", "new-param"],
        ["generic", "insert", '["metadata"]', '{"labels": {"new-param": "value"}}'],
    ],
)
def test_v2_dry_run_does_not_modify_files(
    resource_args, pipeline_and_run_yaml, tmp_path, monkeypatch, capsys
):
    pipeline_file = tmp_path / "pipeline.yaml"
    pipeline_file.write_text(pipeline_and_run_yaml)
    resource, *operation = resource_args

    run_pmt(monkeypatch, "2", resource, "-f", str(pipeline_file), "--dry-run", *operation)

    assert pipeline_file.read_text() == pipeline_and_run_yaml
    assert "new-param" in capsys.readouterr().out


@responses.activate
@pytest.mark.parametrize(
    "v1_options,v2_options,run_after,check_finally",
    [
        pytest.param(["-a", "clone"], ["-a", "clone"], ["clone"], False, id="tasks"),
        # finally tasks cannot run after tasks of the tasks section
        pytest.param(["-f"], ["--finally"], None, True, id="finally"),
    ],
)
def test_v2_task_add_is_equivalent_to_v1_add_task(
    v1_options,
    v2_options,
    run_after,
    check_finally,
    component_a_repo,
    image_manifest,
    tmp_path,
    monkeypatch,
):
    mock_get_digest_for_specific_tag(*TEST_TASK_VALUES)
    mock_get_bundle_image_manifest(BUNDLE_REF, image_manifest)

    v1_file = component_a_repo.tekton_dir / "pr.yaml"
    v2_file = Path(tmp_path / "v2.yaml")
    shutil.copyfile(v1_file, v2_file)

    run_pmt(monkeypatch, None, "add-task", BUNDLE_REF, str(v1_file), *v1_options)
    run_pmt(monkeypatch, "2", "task", "-f", str(v2_file), "add", BUNDLE_REF, *v2_options)

    assert v2_file.read_text() == v1_file.read_text()
    VerifyUpdatedPipeline(
        TASK_NAME, BUNDLE_REF, run_after=run_after, check_finally=check_finally
    ).check(str(v2_file))


@responses.activate
def test_v2_task_add_dry_run(component_a_repo, image_manifest, monkeypatch, capsys):
    mock_get_digest_for_specific_tag(*TEST_TASK_VALUES)
    mock_get_bundle_image_manifest(BUNDLE_REF, image_manifest)
    git_add_calls = []
    monkeypatch.setattr(
        "pipeline_migration.actions.add_task.git_add", lambda *a: git_add_calls.append(a)
    )

    pipeline_file = component_a_repo.tekton_dir / "pr.yaml"
    origin_content = pipeline_file.read_text()

    run_pmt(
        monkeypatch, "2", "task", "-f", str(pipeline_file), "--dry-run", "add", BUNDLE_REF, "-g"
    )

    assert pipeline_file.read_text() == origin_content
    assert f"name: {TASK_NAME}" in capsys.readouterr().out
    assert git_add_calls == []


@pytest.mark.parametrize("api_version", list(ApiVersion))
@pytest.mark.parametrize("resource", ["task", "pipeline", "generic"])
def test_render_resource_description(api_version, resource, capsys):
    """Descriptions are rendered from templates shared by all API versions"""
    prefix = {ApiVersion.V1: ["modify", resource], ApiVersion.V2: [resource]}[api_version]
    with pytest.raises(SystemExit):
        build_parser(api_version).parse_args([*prefix, "--help"])
    out = capsys.readouterr().out

    assert "{{" not in out and "}}" not in out, "unrendered placeholder"
    expected_command = {ApiVersion.V1: f"pmt modify {resource} ", ApiVersion.V2: f"pmt {resource} "}
    assert expected_command[api_version] in out
    other_version = ApiVersion.V2 if api_version == ApiVersion.V1 else ApiVersion.V1
    assert expected_command[other_version] not in out


@pytest.mark.parametrize(
    "api_version,present,absent",
    [
        (ApiVersion.V1, ["matrix-add-param"], ["add-matrix-param", "pmt task add", "reserved"]),
        (ApiVersion.V2, ["add-matrix-param", "pmt task add", "reserved"], ["matrix-add-param"]),
    ],
)
def test_task_description_parts_of_api_version(api_version, present, absent):
    description = subcmd_description(api_version)
    for text in present:
        assert text in description
    for text in absent:
        assert text not in description
