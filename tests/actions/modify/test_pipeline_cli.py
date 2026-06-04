from pathlib import Path
from textwrap import dedent

import pytest

from pipeline_migration.cli import entry_point
from pipeline_migration.utils import load_yaml


class ComponentRepo:
    def __init__(self, base_path: Path):
        self.base_path = base_path
        self.tekton_dir = base_path / ".tekton"


@pytest.fixture
def component_pipeline_dir(tmp_path):
    component_dir = tmp_path / "component_pipeline"
    tekton_dir = component_dir / ".tekton"
    tekton_dir.mkdir(parents=True)

    pipeline_content = dedent("""\
        apiVersion: tekton.dev/v1
        kind: Pipeline
        metadata:
          name: test-pipeline
        spec:
          params:
            - name: git-url
            - name: revision
              default: "main"
          tasks:
            - name: clone
              taskRef:
                name: git-clone
        """)
    pipeline_file = tekton_dir / "pipeline.yaml"
    pipeline_file.write_text(pipeline_content)

    pipeline_run_content = dedent("""\
        apiVersion: tekton.dev/v1
        kind: PipelineRun
        metadata:
          name: test-pipeline-run
        spec:
          pipelineSpec:
            params:
              - name: git-url
              - name: revision
                default: "main"
            tasks:
              - name: clone
                taskRef:
                  name: git-clone
        """)
    pipeline_run_file = tekton_dir / "pipeline-run.yaml"
    pipeline_run_file.write_text(pipeline_run_content)

    return ComponentRepo(component_dir)


@pytest.fixture
def component_no_params_dir(tmp_path):
    component_dir = tmp_path / "component_no_params"
    tekton_dir = component_dir / ".tekton"
    tekton_dir.mkdir(parents=True)

    pipeline_content = dedent("""\
        apiVersion: tekton.dev/v1
        kind: Pipeline
        metadata:
          name: test-pipeline
        spec:
          tasks:
            - name: clone
              taskRef:
                name: git-clone
        """)
    pipeline_file = tekton_dir / "pipeline.yaml"
    pipeline_file.write_text(pipeline_content)

    return ComponentRepo(component_dir)


def verify_pipeline_param_exists(file_path: Path, param_name: str, default=None):
    doc = load_yaml(file_path)

    params = None
    if doc.get("kind") == "Pipeline":
        params = doc.get("spec", {}).get("params")
    elif doc.get("kind") == "PipelineRun":
        params = doc.get("spec", {}).get("pipelineSpec", {}).get("params")

    assert params is not None, f"No params found in {file_path}"

    param = next((p for p in params if p["name"] == param_name), None)
    assert param is not None, f"Parameter {param_name} not found in {file_path}"

    if default is not None:
        assert (
            param.get("default") == default
        ), f"Parameter {param_name} has wrong default in {file_path}"


def verify_pipeline_param_absent(file_path: Path, param_name: str):
    doc = load_yaml(file_path)

    params = None
    if doc.get("kind") == "Pipeline":
        params = doc.get("spec", {}).get("params")
    elif doc.get("kind") == "PipelineRun":
        params = doc.get("spec", {}).get("pipelineSpec", {}).get("params")

    if params is None:
        return

    param = next((p for p in params if p["name"] == param_name), None)
    assert param is None, f"Parameter {param_name} still exists in {file_path}"


class TestCliAddParam:

    def test_add_param(self, component_pipeline_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "add-param",
            "new-param",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        for yaml_file in component_pipeline_dir.tekton_dir.glob("*.yaml"):
            verify_pipeline_param_exists(yaml_file, "new-param")

    def test_add_param_with_default(self, component_pipeline_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "add-param",
            "new-param",
            "--default",
            "my-value",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        for yaml_file in component_pipeline_dir.tekton_dir.glob("*.yaml"):
            verify_pipeline_param_exists(yaml_file, "new-param", default="my-value")

    def test_add_param_with_type(self, component_pipeline_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "add-param",
            "new-param",
            "--default",
            "value",
            "--type",
            "string",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        for yaml_file in component_pipeline_dir.tekton_dir.glob("*.yaml"):
            verify_pipeline_param_exists(yaml_file, "new-param", default="value")

    def test_add_param_array_type(self, component_pipeline_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "add-param",
            "images",
            "--type",
            "array",
            "--default",
            "img1",
            "img2",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        for yaml_file in component_pipeline_dir.tekton_dir.glob("*.yaml"):
            verify_pipeline_param_exists(yaml_file, "images", default=["img1", "img2"])

    def test_add_param_updates_existing(self, component_pipeline_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "add-param",
            "revision",
            "--default",
            "develop",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        for yaml_file in component_pipeline_dir.tekton_dir.glob("*.yaml"):
            verify_pipeline_param_exists(yaml_file, "revision", default="develop")

    def test_add_param_no_params_section(self, component_no_params_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_no_params_dir.tekton_dir),
            "pipeline",
            "add-param",
            "new-param",
            "--default",
            "value",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        pipeline_file = component_no_params_dir.tekton_dir / "pipeline.yaml"
        verify_pipeline_param_exists(pipeline_file, "new-param", default="value")

    def test_add_param_relative_tekton_dir(self, component_pipeline_dir, monkeypatch):
        monkeypatch.chdir(str(component_pipeline_dir.base_path))
        cmd = ["pmt", "modify", "pipeline", "add-param", "new-param", "--default", "val"]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        for yaml_file in component_pipeline_dir.tekton_dir.glob("*.yaml"):
            verify_pipeline_param_exists(yaml_file, "new-param", default="val")

    def test_add_param_specific_file(self, component_pipeline_dir, monkeypatch):
        pipeline_file = component_pipeline_dir.tekton_dir / "pipeline.yaml"
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(pipeline_file),
            "pipeline",
            "add-param",
            "new-param",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        verify_pipeline_param_exists(pipeline_file, "new-param")


class TestCliUpdateParam:

    def test_update_param(self, component_pipeline_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "update-param",
            "revision",
            "--default",
            "develop",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        for yaml_file in component_pipeline_dir.tekton_dir.glob("*.yaml"):
            verify_pipeline_param_exists(yaml_file, "revision", default="develop")

    def test_update_nonexistent_param(self, component_pipeline_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "update-param",
            "nonexistent",
            "--default",
            "value",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        for yaml_file in component_pipeline_dir.tekton_dir.glob("*.yaml"):
            verify_pipeline_param_exists(yaml_file, "git-url")
            verify_pipeline_param_exists(yaml_file, "revision", default="main")

    def test_update_requires_default(self, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "pipeline",
            "update-param",
            "revision",
        ]
        monkeypatch.setattr("sys.argv", cmd)

        with pytest.raises(SystemExit):
            entry_point()

    def test_update_relative_tekton_dir(self, component_pipeline_dir, monkeypatch):
        monkeypatch.chdir(str(component_pipeline_dir.base_path))
        cmd = [
            "pmt",
            "modify",
            "pipeline",
            "update-param",
            "revision",
            "--default",
            "develop",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        for yaml_file in component_pipeline_dir.tekton_dir.glob("*.yaml"):
            verify_pipeline_param_exists(yaml_file, "revision", default="develop")


class TestCliRemoveParam:

    def test_remove_param(self, component_pipeline_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "remove-param",
            "revision",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        for yaml_file in component_pipeline_dir.tekton_dir.glob("*.yaml"):
            verify_pipeline_param_absent(yaml_file, "revision")
            verify_pipeline_param_exists(yaml_file, "git-url")

    def test_remove_nonexistent_param(self, component_pipeline_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "remove-param",
            "nonexistent",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        for yaml_file in component_pipeline_dir.tekton_dir.glob("*.yaml"):
            verify_pipeline_param_exists(yaml_file, "git-url")
            verify_pipeline_param_exists(yaml_file, "revision", default="main")

    def test_remove_all_params(self, component_pipeline_dir, monkeypatch):
        cmd1 = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "remove-param",
            "git-url",
        ]
        monkeypatch.setattr("sys.argv", cmd1)
        entry_point()

        cmd2 = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "remove-param",
            "revision",
        ]
        monkeypatch.setattr("sys.argv", cmd2)
        entry_point()

        for yaml_file in component_pipeline_dir.tekton_dir.glob("*.yaml"):
            verify_pipeline_param_absent(yaml_file, "git-url")
            verify_pipeline_param_absent(yaml_file, "revision")

    def test_remove_relative_tekton_dir(self, component_pipeline_dir, monkeypatch):
        monkeypatch.chdir(str(component_pipeline_dir.base_path))
        cmd = ["pmt", "modify", "pipeline", "remove-param", "revision"]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        for yaml_file in component_pipeline_dir.tekton_dir.glob("*.yaml"):
            verify_pipeline_param_absent(yaml_file, "revision")


class TestCliErrorHandling:

    def test_missing_subcommand(self, monkeypatch):
        cmd = ["pmt", "modify", "pipeline"]
        monkeypatch.setattr("sys.argv", cmd)

        with pytest.raises(SystemExit):
            entry_point()

    def test_missing_param_name(self, monkeypatch):
        cmd = ["pmt", "modify", "pipeline", "add-param"]
        monkeypatch.setattr("sys.argv", cmd)

        with pytest.raises(SystemExit):
            entry_point()

    def test_invalid_subcommand(self, monkeypatch):
        cmd = ["pmt", "modify", "pipeline", "invalid-command"]
        monkeypatch.setattr("sys.argv", cmd)

        with pytest.raises(SystemExit):
            entry_point()

    def test_nonexistent_file_path(self, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            "/nonexistent/path",
            "pipeline",
            "add-param",
            "new-param",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()
