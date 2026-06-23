import pytest
from textwrap import dedent

from pipeline_migration.actions.modify.pipeline import (
    AddPipelineParamOperation,
    UpdatePipelineParamOperation,
    RemovePipelineParamOperation,
    ParamType,
)
from pipeline_migration.utils import load_yaml, YAMLStyle


def read_file_content(file_path: str) -> str:
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def pipeline_yaml_file(create_yaml_file):
    content = dedent("""\
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
    return create_yaml_file(content)


@pytest.fixture
def pipeline_no_params_yaml_file(create_yaml_file):
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
def pipeline_run_yaml_file(create_yaml_file):
    content = dedent("""\
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
    return create_yaml_file(content)


@pytest.fixture
def pipeline_run_no_params_yaml_file(create_yaml_file):
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
def pipeline_typed_params_yaml_file(create_yaml_file):
    content = dedent("""\
        apiVersion: tekton.dev/v1
        kind: Pipeline
        metadata:
          name: test-pipeline
        spec:
          params:
            - name: git-url
              type: string
              default: "https://github.com/example/repo"
            - name: images
              type: array
              default:
                - "image1"
                - "image2"
          tasks:
            - name: clone
              taskRef:
                name: git-clone
        """)
    return create_yaml_file(content)


class TestAddPipelineParamOperation:

    def test_add_param_name_only(self, pipeline_yaml_file):
        op = AddPipelineParamOperation("new-param")
        op.handle(str(pipeline_yaml_file))

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              params:
                - name: git-url
                - name: revision
                  default: "main"
                - name: new-param
              tasks:
                - name: clone
                  taskRef:
                    name: git-clone
            """)
        assert read_file_content(pipeline_yaml_file) == expected

    def test_add_param_with_default(self, pipeline_yaml_file):
        op = AddPipelineParamOperation("new-param", param_default="my-value")
        op.handle(str(pipeline_yaml_file))

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              params:
                - name: git-url
                - name: revision
                  default: "main"
                - name: new-param
                  default: my-value
              tasks:
                - name: clone
                  taskRef:
                    name: git-clone
            """)
        assert read_file_content(pipeline_yaml_file) == expected

    def test_add_param_with_type(self, pipeline_yaml_file):
        op = AddPipelineParamOperation(
            "new-param", param_default="my-value", param_type=ParamType.string
        )
        op.handle(str(pipeline_yaml_file))

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              params:
                - name: git-url
                - name: revision
                  default: "main"
                - name: new-param
                  type: string
                  default: my-value
              tasks:
                - name: clone
                  taskRef:
                    name: git-clone
            """)
        assert read_file_content(pipeline_yaml_file) == expected

    def test_add_param_with_array_default(self, pipeline_yaml_file):
        op = AddPipelineParamOperation(
            "images", param_default=["img1", "img2"], param_type=ParamType.array
        )
        op.handle(str(pipeline_yaml_file))

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              params:
                - name: git-url
                - name: revision
                  default: "main"
                - name: images
                  type: array
                  default:
                    - img1
                    - img2
              tasks:
                - name: clone
                  taskRef:
                    name: git-clone
            """)
        assert read_file_content(pipeline_yaml_file) == expected

    def test_add_param_to_pipeline_without_params(self, pipeline_no_params_yaml_file):
        op = AddPipelineParamOperation("new-param", param_default="value")
        op.handle(str(pipeline_no_params_yaml_file))

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
              params:
                - name: new-param
                  default: value
            """)
        assert read_file_content(pipeline_no_params_yaml_file) == expected

    def test_add_param_updates_existing(self, pipeline_yaml_file):
        op = AddPipelineParamOperation("revision", param_default="develop")
        op.handle(str(pipeline_yaml_file))

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              params:
                - name: git-url
                - name: revision
                  default: develop
              tasks:
                - name: clone
                  taskRef:
                    name: git-clone
            """)
        assert read_file_content(pipeline_yaml_file) == expected

    def test_add_param_no_change_when_same(self, pipeline_yaml_file):
        op = AddPipelineParamOperation("revision", param_default="main")
        op.handle(str(pipeline_yaml_file))

        expected = dedent("""\
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
        assert read_file_content(pipeline_yaml_file) == expected

    def test_add_param_pipeline_run(self, pipeline_run_yaml_file):
        op = AddPipelineParamOperation("new-param", param_default="value")
        op.handle(str(pipeline_run_yaml_file))

        expected = dedent("""\
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
                  - name: new-param
                    default: value
                tasks:
                  - name: clone
                    taskRef:
                      name: git-clone
            """)
        assert read_file_content(pipeline_run_yaml_file) == expected

    def test_add_param_pipeline_run_no_params(self, pipeline_run_no_params_yaml_file):
        op = AddPipelineParamOperation("new-param", param_default="value")
        op.handle(str(pipeline_run_no_params_yaml_file))

        expected = dedent("""\
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
                params:
                  - name: new-param
                    default: value
            """)
        assert read_file_content(pipeline_run_no_params_yaml_file) == expected


class TestUpdatePipelineParamOperation:

    def test_update_existing_param(self, pipeline_yaml_file):
        op = UpdatePipelineParamOperation("revision", "develop")
        op.handle(str(pipeline_yaml_file))

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              params:
                - name: git-url
                - name: revision
                  default: develop
              tasks:
                - name: clone
                  taskRef:
                    name: git-clone
            """)
        assert read_file_content(pipeline_yaml_file) == expected

    def test_update_no_change_when_same(self, pipeline_yaml_file):
        op = UpdatePipelineParamOperation("revision", "main")
        op.handle(str(pipeline_yaml_file))

        expected = dedent("""\
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
        assert read_file_content(pipeline_yaml_file) == expected

    def test_update_nonexistent_param(self, pipeline_yaml_file):
        op = UpdatePipelineParamOperation("nonexistent", "value")
        op.handle(str(pipeline_yaml_file))

        expected = dedent("""\
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
        assert read_file_content(pipeline_yaml_file) == expected

    def test_update_no_params_section(self, pipeline_no_params_yaml_file):
        op = UpdatePipelineParamOperation("nonexistent", "value")
        op.handle(str(pipeline_no_params_yaml_file))

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
        assert read_file_content(pipeline_no_params_yaml_file) == expected

    def test_update_param_pipeline_run(self, pipeline_run_yaml_file):
        op = UpdatePipelineParamOperation("revision", "develop")
        op.handle(str(pipeline_run_yaml_file))

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: PipelineRun
            metadata:
              name: test-pipeline-run
            spec:
              pipelineSpec:
                params:
                  - name: git-url
                  - name: revision
                    default: develop
                tasks:
                  - name: clone
                    taskRef:
                      name: git-clone
            """)
        assert read_file_content(pipeline_run_yaml_file) == expected

    def test_update_preserves_type(self, pipeline_typed_params_yaml_file):
        op = UpdatePipelineParamOperation("git-url", "https://new-url.com")
        op.handle(str(pipeline_typed_params_yaml_file))

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              params:
                - name: git-url
                  type: string
                  default: https://new-url.com
                - name: images
                  type: array
                  default:
                    - "image1"
                    - "image2"
              tasks:
                - name: clone
                  taskRef:
                    name: git-clone
            """)
        assert read_file_content(pipeline_typed_params_yaml_file) == expected

    def test_update_array_param(self, pipeline_typed_params_yaml_file):
        op = UpdatePipelineParamOperation("images", ["new1", "new2", "new3"])
        op.handle(str(pipeline_typed_params_yaml_file))

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              params:
                - name: git-url
                  type: string
                  default: "https://github.com/example/repo"
                - name: images
                  type: array
                  default:
                    - new1
                    - new2
                    - new3
              tasks:
                - name: clone
                  taskRef:
                    name: git-clone
            """)
        assert read_file_content(pipeline_typed_params_yaml_file) == expected


class TestRemovePipelineParamOperation:

    def test_remove_existing_param(self, pipeline_yaml_file):
        op = RemovePipelineParamOperation("revision")
        op.handle(str(pipeline_yaml_file))

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              params:
                - name: git-url
              tasks:
                - name: clone
                  taskRef:
                    name: git-clone
            """)
        assert read_file_content(pipeline_yaml_file) == expected

    def test_remove_nonexistent_param(self, pipeline_yaml_file):
        op = RemovePipelineParamOperation("nonexistent")
        op.handle(str(pipeline_yaml_file))

        expected = dedent("""\
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
        assert read_file_content(pipeline_yaml_file) == expected

    def test_remove_no_params_section(self, pipeline_no_params_yaml_file):
        op = RemovePipelineParamOperation("nonexistent")
        op.handle(str(pipeline_no_params_yaml_file))

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
        assert read_file_content(pipeline_no_params_yaml_file) == expected

    def test_remove_all_params(self, pipeline_yaml_file):
        op1 = RemovePipelineParamOperation("git-url")
        op1.handle(str(pipeline_yaml_file))

        op2 = RemovePipelineParamOperation("revision")
        op2.handle(str(pipeline_yaml_file))

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
        assert read_file_content(pipeline_yaml_file) == expected

    def test_remove_param_pipeline_run(self, pipeline_run_yaml_file):
        op = RemovePipelineParamOperation("revision")
        op.handle(str(pipeline_run_yaml_file))

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: PipelineRun
            metadata:
              name: test-pipeline-run
            spec:
              pipelineSpec:
                params:
                  - name: git-url
                tasks:
                  - name: clone
                    taskRef:
                      name: git-clone
            """)
        assert read_file_content(pipeline_run_yaml_file) == expected

    def test_remove_first_param(self, pipeline_yaml_file):
        op = RemovePipelineParamOperation("git-url")
        op.handle(str(pipeline_yaml_file))

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              params:
                - name: revision
                  default: "main"
              tasks:
                - name: clone
                  taskRef:
                    name: git-clone
            """)
        assert read_file_content(pipeline_yaml_file) == expected


class TestComplexScenarios:

    def test_add_then_remove(self, pipeline_yaml_file):
        op_add = AddPipelineParamOperation("new-param", param_default="value")
        op_add.handle(str(pipeline_yaml_file))

        op_remove = RemovePipelineParamOperation("new-param")
        op_remove.handle(str(pipeline_yaml_file))

        expected = dedent("""\
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
        assert read_file_content(pipeline_yaml_file) == expected

    def test_add_then_update(self, pipeline_yaml_file):
        op_add = AddPipelineParamOperation("new-param", param_default="old-value")
        op_add.handle(str(pipeline_yaml_file))

        op_update = UpdatePipelineParamOperation("new-param", "new-value")
        op_update.handle(str(pipeline_yaml_file))

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              params:
                - name: git-url
                - name: revision
                  default: "main"
                - name: new-param
                  default: new-value
              tasks:
                - name: clone
                  taskRef:
                    name: git-clone
            """)
        assert read_file_content(pipeline_yaml_file) == expected

    def test_multiple_adds(self, pipeline_yaml_file):
        op1 = AddPipelineParamOperation("param1", param_default="val1")
        op1.handle(str(pipeline_yaml_file))

        op2 = AddPipelineParamOperation("param2", param_default="val2")
        op2.handle(str(pipeline_yaml_file))

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              params:
                - name: git-url
                - name: revision
                  default: "main"
                - name: param1
                  default: val1
                - name: param2
                  default: val2
              tasks:
                - name: clone
                  taskRef:
                    name: git-clone
            """)
        assert read_file_content(pipeline_yaml_file) == expected
