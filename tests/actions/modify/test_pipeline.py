import argparse

import pytest
from textwrap import dedent

from ruamel.yaml.scalarstring import LiteralScalarString

from pipeline_migration.actions.modify.pipeline import (
    PipelineAddParamOperation,
    PipelineRemoveParamOperation,
    PipelineAddResultOperation,
    PipelineRemoveResultOperation,
    ResultType,
    _format_description,
    _name_value_pair,
)
from pipeline_migration.actions.modify.common import ParamType


def read_file_content(file_path) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def pipeline_with_params(create_yaml_file):
    content = dedent("""\
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
          tasks:
            - name: clone
              taskRef:
                name: git-clone
        """)
    return create_yaml_file(content)


@pytest.fixture
def pipeline_without_params(create_yaml_file):
    content = dedent("""\
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
    return create_yaml_file(content)


@pytest.fixture
def pipeline_with_results(create_yaml_file):
    content = dedent("""\
        apiVersion: tekton.dev/v1
        kind: Pipeline
        metadata:
          name: test-pipeline
        spec:
          results:
            - name: IMAGE_DIGEST
              type: string
              description: Image digest
              value: $(tasks.build.results.IMAGE_DIGEST)
          tasks:
            - name: build
              taskRef:
                name: buildah
        """)
    return create_yaml_file(content)


@pytest.fixture
def pipeline_without_results(create_yaml_file):
    content = dedent("""\
        apiVersion: tekton.dev/v1
        kind: Pipeline
        metadata:
          name: test-pipeline
        spec:
          params:
            - name: git-url
              type: string
          tasks:
            - name: build
              taskRef:
                name: buildah
        """)
    return create_yaml_file(content)


@pytest.fixture
def pipeline_run_with_params(create_yaml_file):
    content = dedent("""\
        apiVersion: tekton.dev/v1
        kind: PipelineRun
        metadata:
          name: test-pipeline-run
        spec:
          pipelineSpec:
            params:
              - name: git-url
                type: string
                description: Git repository URL
            tasks:
              - name: clone
                taskRef:
                  name: git-clone
        """)
    return create_yaml_file(content)


@pytest.fixture
def pipeline_run_without_params(create_yaml_file):
    content = dedent("""\
        apiVersion: tekton.dev/v1
        kind: PipelineRun
        metadata:
          name: test-pipeline-run
        spec:
          pipelineSpec:
            tasks:
              - name: clone
                taskRef:
                  name: git-clone
        """)
    return create_yaml_file(content)


@pytest.fixture
def pipeline_run_with_results(create_yaml_file):
    content = dedent("""\
        apiVersion: tekton.dev/v1
        kind: PipelineRun
        metadata:
          name: test-pipeline-run
        spec:
          pipelineSpec:
            results:
              - name: IMAGE_DIGEST
                type: string
                description: Image digest
                value: $(tasks.build.results.IMAGE_DIGEST)
            tasks:
              - name: build
                taskRef:
                  name: buildah
        """)
    return create_yaml_file(content)


@pytest.fixture
def pipeline_run_with_param_values(create_yaml_file):
    content = dedent("""\
        apiVersion: tekton.dev/v1
        kind: PipelineRun
        metadata:
          name: test-pipeline-run
        spec:
          params:
            - name: git-url
              value: '{{source_url}}'
            - name: revision
              value: '{{revision}}'
          pipelineSpec:
            params:
              - name: git-url
                type: string
                description: Git repository URL
              - name: revision
                type: string
                description: Git revision
                default: main
            tasks:
              - name: clone
                taskRef:
                  name: git-clone
        """)
    return create_yaml_file(content)


@pytest.fixture
def pipeline_no_indent_style(create_yaml_file):
    content = dedent("""\
        apiVersion: tekton.dev/v1
        kind: Pipeline
        metadata:
          name: test-pipeline
        spec:
          params:
          - name: git-url
            type: string
            description: Git repository URL
          tasks:
          - name: clone
            taskRef:
              name: git-clone
        """)
    return create_yaml_file(content)


class TestFormatDescription:

    def test_single_line(self):
        result = _format_description("A simple description")
        assert result == "A simple description"
        assert isinstance(result, str)

    def test_multiline(self):
        result = _format_description("Line one\nLine two")
        assert isinstance(result, LiteralScalarString)
        assert str(result) == "Line one\nLine two\n"

    def test_multiline_with_trailing_newline(self):
        result = _format_description("Line one\nLine two\n")
        assert isinstance(result, LiteralScalarString)
        assert str(result) == "Line one\nLine two\n"

    def test_empty(self):
        result = _format_description("")
        assert result == ""


class TestNameValuePair:

    def test_valid_pair(self):
        assert _name_value_pair("NAME=value") == ("NAME", "value")

    def test_value_with_equals(self):
        assert _name_value_pair("NAME=a=b") == ("NAME", "a=b")

    def test_expression_value(self):
        name, value = _name_value_pair("DIGEST=$(tasks.build.results.DIGEST)")
        assert name == "DIGEST"
        assert value == "$(tasks.build.results.DIGEST)"

    def test_missing_equals(self):
        with pytest.raises(argparse.ArgumentTypeError, match="Expected name=value"):
            _name_value_pair("no-equals-sign")

    def test_empty_name(self):
        with pytest.raises(argparse.ArgumentTypeError, match="must not be empty"):
            _name_value_pair("=value")


class TestPipelineAddParamOperation:

    def test_add_param_to_existing_params(self, pipeline_with_params):
        op = PipelineAddParamOperation("output-image", ParamType.string, "Output image URL", "")
        op.handle(str(pipeline_with_params))

        expected = dedent("""\
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
                - name: output-image
                  type: string
                  description: Output image URL
                  default: ''
              tasks:
                - name: clone
                  taskRef:
                    name: git-clone
            """)
        assert read_file_content(pipeline_with_params) == expected

    def test_add_param_creates_params_section(self, pipeline_without_params):
        op = PipelineAddParamOperation("git-url", ParamType.string, "Git repository URL", "")
        op.handle(str(pipeline_without_params))

        content = read_file_content(pipeline_without_params)
        assert "params:" in content
        assert "name: git-url" in content
        assert "description: Git repository URL" in content

    def test_add_param_idempotent(self, pipeline_with_params):
        original = read_file_content(pipeline_with_params)
        op = PipelineAddParamOperation("git-url", ParamType.string, "Git repository URL", "")
        op.handle(str(pipeline_with_params))

        assert read_file_content(pipeline_with_params) == original

    def test_add_param_with_string_default(self, pipeline_with_params):
        op = PipelineAddParamOperation("output-image", ParamType.string, "", "quay.io/my/image")
        op.handle(str(pipeline_with_params))

        expected = dedent("""\
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
                - name: output-image
                  type: string
                  default: quay.io/my/image
              tasks:
                - name: clone
                  taskRef:
                    name: git-clone
            """)
        assert read_file_content(pipeline_with_params) == expected

    def test_add_param_with_array_default(self, pipeline_with_params):
        op = PipelineAddParamOperation(
            "platforms", ParamType.array, "", ["linux/amd64", "linux/arm64"]
        )
        op.handle(str(pipeline_with_params))

        expected = dedent("""\
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
                - name: platforms
                  type: array
                  default:
                    - linux/amd64
                    - linux/arm64
              tasks:
                - name: clone
                  taskRef:
                    name: git-clone
            """)
        assert read_file_content(pipeline_with_params) == expected

    def test_add_param_with_empty_array_default(self, pipeline_with_params):
        op = PipelineAddParamOperation("extra-args", ParamType.array, "", [])
        op.handle(str(pipeline_with_params))

        expected = dedent("""\
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
                - name: extra-args
                  type: array
                  default: []
              tasks:
                - name: clone
                  taskRef:
                    name: git-clone
            """)
        assert read_file_content(pipeline_with_params) == expected

    def test_add_param_with_description(self, pipeline_with_params):
        op = PipelineAddParamOperation("output-image", ParamType.string, "The output image URL", "")
        op.handle(str(pipeline_with_params))

        content = read_file_content(pipeline_with_params)
        assert "description: The output image URL" in content

    def test_add_param_without_description(self, pipeline_with_params):
        op = PipelineAddParamOperation("output-image", ParamType.string, "", "")
        op.handle(str(pipeline_with_params))

        expected = dedent("""\
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
                - name: output-image
                  type: string
                  default: ''
              tasks:
                - name: clone
                  taskRef:
                    name: git-clone
            """)
        assert read_file_content(pipeline_with_params) == expected

    def test_add_param_with_multiline_description(self, pipeline_with_params):
        desc = LiteralScalarString("Line one\nLine two\n")
        op = PipelineAddParamOperation("output-image", ParamType.string, desc, "")
        op.handle(str(pipeline_with_params))

        content = read_file_content(pipeline_with_params)
        assert "description: |" in content
        assert "Line one" in content
        assert "Line two" in content

    def test_add_param_on_pipeline_run(self, pipeline_run_with_params):
        op = PipelineAddParamOperation("output-image", ParamType.string, "Output image URL", "")
        op.handle(str(pipeline_run_with_params))

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: PipelineRun
            metadata:
              name: test-pipeline-run
            spec:
              pipelineSpec:
                params:
                  - name: git-url
                    type: string
                    description: Git repository URL
                  - name: output-image
                    type: string
                    description: Output image URL
                    default: ''
                tasks:
                  - name: clone
                    taskRef:
                      name: git-clone
            """)
        assert read_file_content(pipeline_run_with_params) == expected

    def test_add_param_creates_section_on_pipeline_run(self, pipeline_run_without_params):
        op = PipelineAddParamOperation("git-url", ParamType.string, "Git URL", "")
        op.handle(str(pipeline_run_without_params))

        content = read_file_content(pipeline_run_without_params)
        assert "params:" in content
        assert "name: git-url" in content

    def test_add_param_preserves_no_indent_style(self, pipeline_no_indent_style):
        op = PipelineAddParamOperation("output-image", ParamType.string, "Output image URL", "")
        op.handle(str(pipeline_no_indent_style))

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              params:
              - name: git-url
                type: string
                description: Git repository URL
              - name: output-image
                type: string
                description: Output image URL
                default: ''
              tasks:
              - name: clone
                taskRef:
                  name: git-clone
            """)
        assert read_file_content(pipeline_no_indent_style) == expected


class TestPipelineRemoveParamOperation:

    def test_remove_existing_param(self, pipeline_with_params):
        op = PipelineRemoveParamOperation("revision")
        op.handle(str(pipeline_with_params))

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              params:
                - name: git-url
                  type: string
                  description: Git repository URL
              tasks:
                - name: clone
                  taskRef:
                    name: git-clone
            """)
        assert read_file_content(pipeline_with_params) == expected

    def test_remove_nonexistent_param_is_noop(self, pipeline_with_params):
        original = read_file_content(pipeline_with_params)
        op = PipelineRemoveParamOperation("nonexistent")
        op.handle(str(pipeline_with_params))

        assert read_file_content(pipeline_with_params) == original

    def test_remove_from_pipeline_without_params(self, pipeline_without_params):
        original = read_file_content(pipeline_without_params)
        op = PipelineRemoveParamOperation("git-url")
        op.handle(str(pipeline_without_params))

        assert read_file_content(pipeline_without_params) == original

    def test_remove_param_on_pipeline_run(self, pipeline_run_with_params):
        op = PipelineRemoveParamOperation("git-url")
        op.handle(str(pipeline_run_with_params))

        content = read_file_content(pipeline_run_with_params)
        assert "git-url" not in content
        assert "kind: PipelineRun" in content

    def test_remove_param_on_pipeline_run_removes_values(self, pipeline_run_with_param_values):
        op = PipelineRemoveParamOperation("revision")
        op.handle(str(pipeline_run_with_param_values))

        expected = dedent("""\
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
                tasks:
                  - name: clone
                    taskRef:
                      name: git-clone
            """)
        assert read_file_content(pipeline_run_with_param_values) == expected

    def test_remove_param_on_pipeline_run_without_params(self, pipeline_run_without_params):
        original = read_file_content(pipeline_run_without_params)
        op = PipelineRemoveParamOperation("git-url")
        op.handle(str(pipeline_run_without_params))

        assert read_file_content(pipeline_run_without_params) == original

    def test_remove_param_preserves_no_indent_style(self, pipeline_no_indent_style):
        op = PipelineRemoveParamOperation("git-url")
        op.handle(str(pipeline_no_indent_style))

        expected = dedent("""\
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
        assert read_file_content(pipeline_no_indent_style) == expected


class TestPipelineAddResultOperation:

    def test_add_result_to_existing_results(self, pipeline_with_results):
        op = PipelineAddResultOperation(
            "IMAGE_URL",
            "$(tasks.build.results.IMAGE_URL)",
            ResultType.string,
            "Image URL",
        )
        op.handle(str(pipeline_with_results))

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              results:
                - name: IMAGE_DIGEST
                  type: string
                  description: Image digest
                  value: $(tasks.build.results.IMAGE_DIGEST)
                - name: IMAGE_URL
                  type: string
                  description: Image URL
                  value: $(tasks.build.results.IMAGE_URL)
              tasks:
                - name: build
                  taskRef:
                    name: buildah
            """)
        assert read_file_content(pipeline_with_results) == expected

    def test_add_result_creates_results_section(self, pipeline_without_results):
        op = PipelineAddResultOperation(
            "IMAGE_DIGEST",
            "$(tasks.build.results.IMAGE_DIGEST)",
            ResultType.string,
            "Image digest",
        )
        op.handle(str(pipeline_without_results))

        content = read_file_content(pipeline_without_results)
        assert "results:" in content
        assert "name: IMAGE_DIGEST" in content
        assert "value: $(tasks.build.results.IMAGE_DIGEST)" in content

    def test_add_result_idempotent(self, pipeline_with_results):
        original = read_file_content(pipeline_with_results)
        op = PipelineAddResultOperation(
            "IMAGE_DIGEST",
            "$(tasks.build.results.IMAGE_DIGEST)",
            ResultType.string,
            "Image digest",
        )
        op.handle(str(pipeline_with_results))

        assert read_file_content(pipeline_with_results) == original

    def test_add_result_with_different_value_warns(self, pipeline_with_results, caplog):
        original = read_file_content(pipeline_with_results)
        op = PipelineAddResultOperation(
            "IMAGE_DIGEST",
            "$(tasks.new-build.results.IMAGE_DIGEST)",
            ResultType.string,
            "",
        )
        op.handle(str(pipeline_with_results))

        assert read_file_content(pipeline_with_results) == original
        assert "different value" in caplog.text
        assert "$(tasks.new-build.results.IMAGE_DIGEST)" in caplog.text

    def test_add_result_with_description(self, pipeline_with_results):
        op = PipelineAddResultOperation(
            "IMAGE_URL",
            "$(tasks.build.results.IMAGE_URL)",
            ResultType.string,
            "The built image URL",
        )
        op.handle(str(pipeline_with_results))

        content = read_file_content(pipeline_with_results)
        assert "description: The built image URL" in content

    def test_add_result_without_description(self, pipeline_with_results):
        op = PipelineAddResultOperation(
            "IMAGE_URL",
            "$(tasks.build.results.IMAGE_URL)",
            ResultType.string,
            "",
        )
        op.handle(str(pipeline_with_results))

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              results:
                - name: IMAGE_DIGEST
                  type: string
                  description: Image digest
                  value: $(tasks.build.results.IMAGE_DIGEST)
                - name: IMAGE_URL
                  type: string
                  value: $(tasks.build.results.IMAGE_URL)
              tasks:
                - name: build
                  taskRef:
                    name: buildah
            """)
        assert read_file_content(pipeline_with_results) == expected

    def test_add_result_with_multiline_description(self, pipeline_with_results):
        desc = LiteralScalarString("Image URL\nfor the built container\n")
        op = PipelineAddResultOperation(
            "IMAGE_URL",
            "$(tasks.build.results.IMAGE_URL)",
            ResultType.string,
            desc,
        )
        op.handle(str(pipeline_with_results))

        content = read_file_content(pipeline_with_results)
        assert "description: |" in content
        assert "Image URL" in content
        assert "for the built container" in content

    def test_add_result_with_object_type(self, pipeline_with_results):
        op = PipelineAddResultOperation(
            "BUILD_OUTPUT",
            "$(tasks.build.results.BUILD_OUTPUT)",
            ResultType.object,
            "",
        )
        op.handle(str(pipeline_with_results))

        content = read_file_content(pipeline_with_results)
        assert "type: object" in content

    def test_add_result_with_object_value(self, pipeline_with_results):
        op = PipelineAddResultOperation(
            "BUILD_OUTPUT",
            {"image_url": "$(tasks.build.results.IMAGE_URL)"},
            ResultType.object,
            "",
        )
        op.handle(str(pipeline_with_results))

        content = read_file_content(pipeline_with_results)
        assert "name: BUILD_OUTPUT" in content
        assert "type: object" in content
        assert "image_url:" in content

    def test_add_result_with_array_value(self, pipeline_with_results):
        op = PipelineAddResultOperation(
            "IMAGES",
            ["$(tasks.foo.results.bar)", "$(tasks.spam.results.egg)"],
            ResultType.array,
            "",
        )
        op.handle(str(pipeline_with_results))

        content = read_file_content(pipeline_with_results)
        assert "name: IMAGES" in content
        assert "type: array" in content

    def test_add_result_on_pipeline_run(self, pipeline_run_with_results):
        op = PipelineAddResultOperation(
            "IMAGE_URL",
            "$(tasks.build.results.IMAGE_URL)",
            ResultType.string,
            "Image URL",
        )
        op.handle(str(pipeline_run_with_results))

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: PipelineRun
            metadata:
              name: test-pipeline-run
            spec:
              pipelineSpec:
                results:
                  - name: IMAGE_DIGEST
                    type: string
                    description: Image digest
                    value: $(tasks.build.results.IMAGE_DIGEST)
                  - name: IMAGE_URL
                    type: string
                    description: Image URL
                    value: $(tasks.build.results.IMAGE_URL)
                tasks:
                  - name: build
                    taskRef:
                      name: buildah
            """)
        assert read_file_content(pipeline_run_with_results) == expected

    def test_add_result_creates_section_on_pipeline_run(self, pipeline_run_without_params):
        op = PipelineAddResultOperation(
            "IMAGE_DIGEST",
            "$(tasks.build.results.IMAGE_DIGEST)",
            ResultType.string,
            "Image digest",
        )
        op.handle(str(pipeline_run_without_params))

        content = read_file_content(pipeline_run_without_params)
        assert "results:" in content
        assert "name: IMAGE_DIGEST" in content
        assert "value: $(tasks.build.results.IMAGE_DIGEST)" in content


class TestPipelineRemoveResultOperation:

    def test_remove_existing_result(self, pipeline_with_results):
        op = PipelineRemoveResultOperation("IMAGE_DIGEST")
        op.handle(str(pipeline_with_results))

        content = read_file_content(pipeline_with_results)
        assert "IMAGE_DIGEST" not in content

    def test_remove_nonexistent_result_is_noop(self, pipeline_with_results):
        original = read_file_content(pipeline_with_results)
        op = PipelineRemoveResultOperation("NONEXISTENT")
        op.handle(str(pipeline_with_results))

        assert read_file_content(pipeline_with_results) == original

    def test_remove_from_pipeline_without_results(self, pipeline_without_results):
        original = read_file_content(pipeline_without_results)
        op = PipelineRemoveResultOperation("IMAGE_DIGEST")
        op.handle(str(pipeline_without_results))

        assert read_file_content(pipeline_without_results) == original

    def test_remove_result_on_pipeline_run(self, pipeline_run_with_results):
        op = PipelineRemoveResultOperation("IMAGE_DIGEST")
        op.handle(str(pipeline_run_with_results))

        content = read_file_content(pipeline_run_with_results)
        assert "IMAGE_DIGEST" not in content
        assert "kind: PipelineRun" in content

    def test_remove_result_on_pipeline_run_without_results(self, pipeline_run_without_params):
        original = read_file_content(pipeline_run_without_params)
        op = PipelineRemoveResultOperation("IMAGE_DIGEST")
        op.handle(str(pipeline_run_without_params))

        assert read_file_content(pipeline_run_without_params) == original


class TestRemoveLastItem:

    def test_remove_last_param_drops_section(self, create_yaml_file):
        content = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              params:
                - name: only-param
                  type: string
                  description: The only parameter
              tasks:
                - name: clone
                  taskRef:
                    name: git-clone
            """)
        yaml_file = create_yaml_file(content)
        op = PipelineRemoveParamOperation("only-param")
        op.handle(str(yaml_file))

        result = read_file_content(yaml_file)
        assert "params" not in result
        assert "tasks:" in result

    def test_remove_last_result_drops_section(self, create_yaml_file):
        content = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              results:
                - name: IMAGE_DIGEST
                  type: string
                  description: Image digest
                  value: $(tasks.build.results.IMAGE_DIGEST)
              tasks:
                - name: build
                  taskRef:
                    name: buildah
            """)
        yaml_file = create_yaml_file(content)
        op = PipelineRemoveResultOperation("IMAGE_DIGEST")
        op.handle(str(yaml_file))

        result = read_file_content(yaml_file)
        assert "results" not in result
        assert "tasks:" in result


class TestAddThenRemoveRoundtrip:

    def test_add_param_then_remove_restores_original(self, pipeline_with_params):
        original = read_file_content(pipeline_with_params)

        add_op = PipelineAddParamOperation("temp-param", ParamType.string, "Temporary", "")
        add_op.handle(str(pipeline_with_params))
        assert "temp-param" in read_file_content(pipeline_with_params)

        remove_op = PipelineRemoveParamOperation("temp-param")
        remove_op.handle(str(pipeline_with_params))
        assert read_file_content(pipeline_with_params) == original

    def test_add_result_then_remove_restores_original(self, pipeline_with_results):
        original = read_file_content(pipeline_with_results)

        add_op = PipelineAddResultOperation(
            "TEMP",
            "$(tasks.build.results.TEMP)",
            ResultType.string,
            "",
        )
        add_op.handle(str(pipeline_with_results))
        assert "TEMP" in read_file_content(pipeline_with_results)

        remove_op = PipelineRemoveResultOperation("TEMP")
        remove_op.handle(str(pipeline_with_results))
        assert read_file_content(pipeline_with_results) == original

    def test_roundtrip_on_pipeline_run(self, pipeline_run_with_params):
        original = read_file_content(pipeline_run_with_params)

        add_op = PipelineAddParamOperation("temp-param", ParamType.string, "Temporary", "")
        add_op.handle(str(pipeline_run_with_params))
        assert "temp-param" in read_file_content(pipeline_run_with_params)

        remove_op = PipelineRemoveParamOperation("temp-param")
        remove_op.handle(str(pipeline_run_with_params))
        assert read_file_content(pipeline_run_with_params) == original

    def test_result_roundtrip_on_pipeline_run(self, pipeline_run_with_results):
        original = read_file_content(pipeline_run_with_results)

        add_op = PipelineAddResultOperation(
            "TEMP",
            "$(tasks.build.results.TEMP)",
            ResultType.string,
            "",
        )
        add_op.handle(str(pipeline_run_with_results))
        assert "TEMP" in read_file_content(pipeline_run_with_results)

        remove_op = PipelineRemoveResultOperation("TEMP")
        remove_op.handle(str(pipeline_run_with_results))
        assert read_file_content(pipeline_run_with_results) == original
