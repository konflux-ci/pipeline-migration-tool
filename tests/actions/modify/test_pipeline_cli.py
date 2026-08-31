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
    component_dir = tmp_path / "component"
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
              type: string
              description: Git repository URL
            - name: revision
              type: string
              description: Git revision
              default: main
          results:
            - name: IMAGE_DIGEST
              type: string
              description: Image digest
              value: $(tasks.build.results.IMAGE_DIGEST)
          tasks:
            - name: clone
              taskRef:
                name: git-clone
            - name: build
              taskRef:
                name: buildah
        """)
    (tekton_dir / "pipeline.yaml").write_text(pipeline_content)

    pipeline_run_content = dedent("""\
        apiVersion: tekton.dev/v1
        kind: PipelineRun
        metadata:
          name: test-pipeline-run
        spec:
          params:
            - name: git-url
              value: '{{source_url}}'
          pipelineSpec:
            params:
              - name: git-url
                type: string
                description: Git repository URL
            results:
              - name: IMAGE_DIGEST
                type: string
                description: Image digest
                value: $(tasks.build.results.IMAGE_DIGEST)
            tasks:
              - name: clone
                taskRef:
                  name: git-clone
              - name: build
                taskRef:
                  name: buildah
        """)
    (tekton_dir / "pipeline-run.yaml").write_text(pipeline_run_content)

    return ComponentRepo(component_dir)


@pytest.fixture
def minimal_pipeline_dir(tmp_path):
    component_dir = tmp_path / "minimal"
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
    (tekton_dir / "pipeline.yaml").write_text(pipeline_content)

    return ComponentRepo(component_dir)


def _get_pipeline_params(file_path: Path):
    doc = load_yaml(file_path)
    if doc.get("kind") == "Pipeline":
        return doc.get("spec", {}).get("params", [])
    return doc.get("spec", {}).get("pipelineSpec", {}).get("params", [])


def _get_pipeline_results(file_path: Path):
    doc = load_yaml(file_path)
    if doc.get("kind") == "Pipeline":
        return doc.get("spec", {}).get("results", [])
    return doc.get("spec", {}).get("pipelineSpec", {}).get("results", [])


class TestModifyPipelineAddParam:

    def test_add_param(self, component_pipeline_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "add-param",
            "--default",
            "",
            "output-image",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        for yaml_file in component_pipeline_dir.tekton_dir.glob("*.yaml"):
            params = _get_pipeline_params(yaml_file)
            names = [p["name"] for p in params]
            assert "output-image" in names

    def test_add_param_with_type_and_description(self, component_pipeline_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "add-param",
            "--type",
            "array",
            "--description",
            "Build platforms",
            "--default",
            "",
            "platforms",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        for yaml_file in component_pipeline_dir.tekton_dir.glob("*.yaml"):
            params = _get_pipeline_params(yaml_file)
            param = next(p for p in params if p["name"] == "platforms")
            assert param["type"] == "array"
            assert param["description"] == "Build platforms"

    def test_add_param_with_string_default(self, component_pipeline_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "add-param",
            "--default",
            "quay.io/my/image",
            "output-image",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        pipeline_file = component_pipeline_dir.tekton_dir / "pipeline.yaml"
        params = _get_pipeline_params(pipeline_file)
        param = next(p for p in params if p["name"] == "output-image")
        assert param["default"] == "quay.io/my/image"

    def test_add_param_with_array_default(self, component_pipeline_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "add-param",
            "--type",
            "array",
            "--default",
            '["linux/amd64","linux/arm64"]',
            "platforms",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        pipeline_file = component_pipeline_dir.tekton_dir / "pipeline.yaml"
        params = _get_pipeline_params(pipeline_file)
        param = next(p for p in params if p["name"] == "platforms")
        assert param["default"] == ["linux/amd64", "linux/arm64"]

    def test_add_param_with_empty_array_default(self, component_pipeline_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "add-param",
            "--type",
            "array",
            "--default",
            "",
            "extra-args",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        pipeline_file = component_pipeline_dir.tekton_dir / "pipeline.yaml"
        params = _get_pipeline_params(pipeline_file)
        param = next(p for p in params if p["name"] == "extra-args")
        assert param["default"] == []

    def test_add_param_idempotent(self, component_pipeline_dir, monkeypatch):
        pipeline_file = component_pipeline_dir.tekton_dir / "pipeline.yaml"
        original = pipeline_file.read_text()

        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "add-param",
            "--default",
            "",
            "git-url",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        assert pipeline_file.read_text() == original

    def test_add_param_creates_section(self, minimal_pipeline_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(minimal_pipeline_dir.tekton_dir),
            "pipeline",
            "add-param",
            "--description",
            "Git URL",
            "--default",
            "",
            "git-url",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        pipeline_file = minimal_pipeline_dir.tekton_dir / "pipeline.yaml"
        params = _get_pipeline_params(pipeline_file)
        assert len(params) == 1
        assert params[0]["name"] == "git-url"

    def test_add_param_uses_relative_tekton_dir(self, component_pipeline_dir, monkeypatch):
        monkeypatch.chdir(str(component_pipeline_dir.base_path))
        cmd = ["pmt", "modify", "pipeline", "add-param", "--default", "", "output-image"]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        for yaml_file in component_pipeline_dir.tekton_dir.glob("*.yaml"):
            params = _get_pipeline_params(yaml_file)
            names = [p["name"] for p in params]
            assert "output-image" in names

    def test_add_param_with_multiline_description(self, component_pipeline_dir, monkeypatch):
        multiline = "Line one\nLine two"
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "add-param",
            "--description",
            multiline,
            "--default",
            "",
            "output-image",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        pipeline_file = component_pipeline_dir.tekton_dir / "pipeline.yaml"
        content = pipeline_file.read_text()
        assert "description: |" in content

    def test_add_param_with_empty_string_default(self, component_pipeline_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "add-param",
            "--default",
            "",
            "output-image",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        pipeline_file = component_pipeline_dir.tekton_dir / "pipeline.yaml"
        params = _get_pipeline_params(pipeline_file)
        param = next(p for p in params if p["name"] == "output-image")
        assert param["default"] == ""

    def test_missing_default(self, monkeypatch):
        cmd = ["pmt", "modify", "pipeline", "add-param", "my-param"]
        monkeypatch.setattr("sys.argv", cmd)

        with pytest.raises(SystemExit):
            entry_point()

    def test_missing_param_name(self, monkeypatch):
        cmd = ["pmt", "modify", "pipeline", "add-param", "--default", ""]
        monkeypatch.setattr("sys.argv", cmd)

        with pytest.raises(SystemExit):
            entry_point()

    def test_invalid_type(self, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "pipeline",
            "add-param",
            "--type",
            "invalid",
            "--default",
            "",
            "my-param",
        ]
        monkeypatch.setattr("sys.argv", cmd)

        with pytest.raises(SystemExit):
            entry_point()

    def test_invalid_json_array_default(self, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "pipeline",
            "add-param",
            "--type",
            "array",
            "--default",
            "not-valid-json",
            "my-param",
        ]
        monkeypatch.setattr("sys.argv", cmd)

        with pytest.raises(SystemExit, match="JSON array"):
            entry_point()

    def test_non_list_json_array_default(self, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "pipeline",
            "add-param",
            "--type",
            "array",
            "--default",
            '"just a string"',
            "my-param",
        ]
        monkeypatch.setattr("sys.argv", cmd)

        with pytest.raises(SystemExit, match="JSON array"):
            entry_point()


class TestModifyPipelineRemoveParam:

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
            params = _get_pipeline_params(yaml_file)
            names = [p["name"] for p in params]
            assert "revision" not in names

    def test_remove_nonexistent_param(self, component_pipeline_dir, monkeypatch):
        pipeline_file = component_pipeline_dir.tekton_dir / "pipeline.yaml"
        original = pipeline_file.read_text()

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

        assert pipeline_file.read_text() == original

    def test_remove_param_uses_relative_tekton_dir(self, component_pipeline_dir, monkeypatch):
        monkeypatch.chdir(str(component_pipeline_dir.base_path))
        cmd = ["pmt", "modify", "pipeline", "remove-param", "revision"]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        for yaml_file in component_pipeline_dir.tekton_dir.glob("*.yaml"):
            params = _get_pipeline_params(yaml_file)
            names = [p["name"] for p in params]
            assert "revision" not in names

    def test_remove_param_cleans_pipeline_run_values(self, component_pipeline_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "remove-param",
            "git-url",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        pipeline_run_file = component_pipeline_dir.tekton_dir / "pipeline-run.yaml"
        doc = load_yaml(pipeline_run_file)
        spec_params = doc.get("spec", {}).get("params", [])
        spec_param_names = [p["name"] for p in spec_params]
        assert "git-url" not in spec_param_names

        pipelinespec_params = doc.get("spec", {}).get("pipelineSpec", {}).get("params", [])
        pipelinespec_param_names = [p["name"] for p in pipelinespec_params]
        assert "git-url" not in pipelinespec_param_names

    def test_missing_param_name(self, monkeypatch):
        cmd = ["pmt", "modify", "pipeline", "remove-param"]
        monkeypatch.setattr("sys.argv", cmd)

        with pytest.raises(SystemExit):
            entry_point()


class TestModifyPipelineAddResult:

    def test_add_result(self, component_pipeline_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "add-result",
            "IMAGE_URL=$(tasks.build.results.IMAGE_URL)",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        for yaml_file in component_pipeline_dir.tekton_dir.glob("*.yaml"):
            results = _get_pipeline_results(yaml_file)
            names = [r["name"] for r in results]
            assert "IMAGE_URL" in names

    def test_add_result_with_type_and_description(self, component_pipeline_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "add-result",
            "--type",
            "object",
            "--description",
            "Build output metadata",
            "BUILD_OUTPUT=$(tasks.build.results.BUILD_OUTPUT)",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        pipeline_file = component_pipeline_dir.tekton_dir / "pipeline.yaml"
        results = _get_pipeline_results(pipeline_file)
        result = next(r for r in results if r["name"] == "BUILD_OUTPUT")
        assert result["type"] == "object"
        assert result["description"] == "Build output metadata"

    def test_add_result_with_array_value(self, component_pipeline_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "add-result",
            "--type",
            "array",
            'IMAGES=["$(tasks.foo.results.bar)","$(tasks.spam.results.egg)"]',
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        pipeline_file = component_pipeline_dir.tekton_dir / "pipeline.yaml"
        results = _get_pipeline_results(pipeline_file)
        result = next(r for r in results if r["name"] == "IMAGES")
        assert result["type"] == "array"
        assert result["value"] == [
            "$(tasks.foo.results.bar)",
            "$(tasks.spam.results.egg)",
        ]

    def test_add_result_with_object_value(self, component_pipeline_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "add-result",
            "--type",
            "object",
            'BUILD_OUTPUT={"image_url":"$(tasks.build.results.IMAGE_URL)"}',
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        pipeline_file = component_pipeline_dir.tekton_dir / "pipeline.yaml"
        results = _get_pipeline_results(pipeline_file)
        result = next(r for r in results if r["name"] == "BUILD_OUTPUT")
        assert result["type"] == "object"
        assert result["value"] == {"image_url": "$(tasks.build.results.IMAGE_URL)"}

    def test_add_result_non_list_json_value_kept_as_string(
        self, component_pipeline_dir, monkeypatch
    ):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "add-result",
            "COUNT=42",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        pipeline_file = component_pipeline_dir.tekton_dir / "pipeline.yaml"
        results = _get_pipeline_results(pipeline_file)
        result = next(r for r in results if r["name"] == "COUNT")
        assert result["value"] == "42"

    def test_add_result_idempotent(self, component_pipeline_dir, monkeypatch):
        pipeline_file = component_pipeline_dir.tekton_dir / "pipeline.yaml"
        original = pipeline_file.read_text()

        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "add-result",
            "IMAGE_DIGEST=$(tasks.build.results.IMAGE_DIGEST)",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        assert pipeline_file.read_text() == original

    def test_add_result_creates_section(self, minimal_pipeline_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(minimal_pipeline_dir.tekton_dir),
            "pipeline",
            "add-result",
            "--description",
            "Image digest",
            "IMAGE_DIGEST=$(tasks.build.results.IMAGE_DIGEST)",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        pipeline_file = minimal_pipeline_dir.tekton_dir / "pipeline.yaml"
        results = _get_pipeline_results(pipeline_file)
        assert len(results) == 1
        assert results[0]["name"] == "IMAGE_DIGEST"
        assert results[0]["value"] == "$(tasks.build.results.IMAGE_DIGEST)"

    def test_add_result_uses_relative_tekton_dir(self, component_pipeline_dir, monkeypatch):
        monkeypatch.chdir(str(component_pipeline_dir.base_path))
        cmd = [
            "pmt",
            "modify",
            "pipeline",
            "add-result",
            "IMAGE_URL=$(tasks.build.results.IMAGE_URL)",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        for yaml_file in component_pipeline_dir.tekton_dir.glob("*.yaml"):
            results = _get_pipeline_results(yaml_file)
            names = [r["name"] for r in results]
            assert "IMAGE_URL" in names

    def test_add_result_with_multiline_description(self, component_pipeline_dir, monkeypatch):
        multiline = "Image URL\nfor the built container"
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "add-result",
            "--description",
            multiline,
            "IMAGE_URL=$(tasks.build.results.IMAGE_URL)",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        pipeline_file = component_pipeline_dir.tekton_dir / "pipeline.yaml"
        content = pipeline_file.read_text()
        assert "description: |" in content

    def test_invalid_name_value_format(self, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "pipeline",
            "add-result",
            "no-equals-sign",
        ]
        monkeypatch.setattr("sys.argv", cmd)

        with pytest.raises(SystemExit):
            entry_point()

    def test_invalid_result_type(self, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "pipeline",
            "add-result",
            "--type",
            "invalid",
            "X=$(tasks.a.results.X)",
        ]
        monkeypatch.setattr("sys.argv", cmd)

        with pytest.raises(SystemExit):
            entry_point()

    def test_missing_name_value_pair(self, monkeypatch):
        cmd = ["pmt", "modify", "pipeline", "add-result"]
        monkeypatch.setattr("sys.argv", cmd)

        with pytest.raises(SystemExit):
            entry_point()


class TestModifyPipelineRemoveResult:

    def test_remove_result(self, component_pipeline_dir, monkeypatch):
        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "remove-result",
            "IMAGE_DIGEST",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        for yaml_file in component_pipeline_dir.tekton_dir.glob("*.yaml"):
            results = _get_pipeline_results(yaml_file)
            names = [r["name"] for r in results]
            assert "IMAGE_DIGEST" not in names

    def test_remove_nonexistent_result(self, component_pipeline_dir, monkeypatch):
        pipeline_file = component_pipeline_dir.tekton_dir / "pipeline.yaml"
        original = pipeline_file.read_text()

        cmd = [
            "pmt",
            "modify",
            "--file-or-dir",
            str(component_pipeline_dir.tekton_dir),
            "pipeline",
            "remove-result",
            "NONEXISTENT",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        assert pipeline_file.read_text() == original

    def test_remove_result_uses_relative_tekton_dir(self, component_pipeline_dir, monkeypatch):
        monkeypatch.chdir(str(component_pipeline_dir.base_path))
        cmd = ["pmt", "modify", "pipeline", "remove-result", "IMAGE_DIGEST"]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()

        for yaml_file in component_pipeline_dir.tekton_dir.glob("*.yaml"):
            results = _get_pipeline_results(yaml_file)
            names = [r["name"] for r in results]
            assert "IMAGE_DIGEST" not in names

    def test_missing_result_name(self, monkeypatch):
        cmd = ["pmt", "modify", "pipeline", "remove-result"]
        monkeypatch.setattr("sys.argv", cmd)

        with pytest.raises(SystemExit):
            entry_point()


class TestModifyPipelineSubcommandErrors:

    def test_missing_subcommand(self, monkeypatch):
        cmd = ["pmt", "modify", "pipeline"]
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
            "--default",
            "",
            "git-url",
        ]
        monkeypatch.setattr("sys.argv", cmd)
        entry_point()
