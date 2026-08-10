import pytest
from textwrap import dedent

from pipeline_migration.actions.modify.task import (
    ModTaskAddParamOperation,
    ModTaskRemoveParamOperation,
    ModTaskMatrixAddParamOperation,
    ModTaskMatrixRemoveParamOperation,
    ModTaskRenameOperation,
    ModTaskSetBundleOperation,
    TaskNotFoundError,
    DuplicateTaskNameError,
)
from pipeline_migration.utils import load_yaml, YAMLStyle


def read_file_content(file_path: str) -> str:
    """Helper function to read file content."""
    with open(file_path, "r", encoding="utf-8") as f:
        return f.read()


@pytest.fixture
def pipeline_yaml_file(create_yaml_file):
    """Create a temporary YAML file with a pipeline structure."""
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
              params:
                - name: url
                  value: "https://github.com/example/repo"
                - name: revision
                  value: "main"
            - name: build
              taskRef:
                name: buildah
              params:
                - name: IMAGE
                  value: "registry.io/app:latest"
            - name: test-task
              taskRef:
                name: test-runner
        """)
    return create_yaml_file(content)


@pytest.fixture
def pipeline_finally_yaml_file(create_yaml_file):
    """Create a temporary YAML file with a pipeline structure."""
    content = dedent("""\
        apiVersion: tekton.dev/v1
        kind: Pipeline
        metadata:
          name: test-pipeline
        spec:
          finally:
            - name: clone
              taskRef:
                name: git-clone
              params:
                - name: url
                  value: "https://github.com/example/repo"
                - name: revision
                  value: "main"
            - name: build
              taskRef:
                name: buildah
              params:
                - name: IMAGE
                  value: "registry.io/app:latest"
            - name: test-task
              taskRef:
                name: test-runner
        """)
    return create_yaml_file(content)


@pytest.fixture
def pipeline_run_yaml_file(create_yaml_file):
    """Create a temporary YAML file with a PipelineRun structure."""
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
                params:
                  - name: url
                    value: "https://github.com/example/repo"
              - name: build
                taskRef:
                  name: buildah
              - name: deploy
                taskRef:
                  name: kubectl-deploy
                params:
                  - name: image
                    value: "registry.io/app:latest"
                  - name: namespace
                    value: "production"
        """)
    return create_yaml_file(content)


@pytest.fixture
def pipeline_run_finally_yaml_file(create_yaml_file):
    """Create a temporary YAML file with a PipelineRun structure."""
    content = dedent("""\
        apiVersion: tekton.dev/v1
        kind: PipelineRun
        metadata:
          name: test-pipeline-run
        spec:
          pipelineSpec:
            finally:
              - name: clone
                taskRef:
                  name: git-clone
                params:
                  - name: url
                    value: "https://github.com/example/repo"
              - name: build
                taskRef:
                  name: buildah
              - name: deploy
                taskRef:
                  name: kubectl-deploy
                params:
                  - name: image
                    value: "registry.io/app:latest"
                  - name: namespace
                    value: "production"
        """)
    return create_yaml_file(content)


@pytest.fixture
def pipeline_matrix_yaml_file(create_yaml_file):
    """Create a temporary YAML file with a pipeline structure."""
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
              matrix:
                params:
                  - name: revision
                    value:
                    - "main"
                    - "test"
            - name: test-task
              taskRef:
                name: test-runner
        """)
    return create_yaml_file(content)


@pytest.fixture
def pipeline_matrix_finally_yaml_file(create_yaml_file):
    """Create a temporary YAML file with a pipeline structure."""
    content = dedent("""\
        apiVersion: tekton.dev/v1
        kind: Pipeline
        metadata:
          name: test-pipeline
        spec:
          finally:
            - name: clone
              taskRef:
                name: git-clone
              matrix:
                params:
                  - name: revision
                    value:
                    - "main"
                    - "test"
            - name: test-task
              taskRef:
                name: test-runner
        """)
    return create_yaml_file(content)


@pytest.fixture
def pipeline_run_matrix_yaml_file(create_yaml_file):
    """Create a temporary YAML file with a PipelineRun structure."""
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
                matrix:
                  params:
                    - name: revision
                      value:
                      - "main"
                      - "test"
              - name: test-task
                taskRef:
                  name: test-runner
        """)
    return create_yaml_file(content)


@pytest.fixture
def pipeline_run_matrix_include_only_yaml_file(create_yaml_file):
    """Create a temporary YAML file with a PipelineRun structure."""
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
                matrix:
                  include:
                    - name: test-one
                      params:
                      - name: url
                        value: $(params.url)
              - name: test-task
                taskRef:
                  name: test-runner
        """)
    return create_yaml_file(content)


@pytest.fixture
def pipeline_run_matrix_finally_yaml_file(create_yaml_file):
    """Create a temporary YAML file with a PipelineRun structure."""
    content = dedent("""\
        apiVersion: tekton.dev/v1
        kind: PipelineRun
        metadata:
          name: test-pipeline-run
        spec:
          pipelineSpec:
            finally:
              - name: clone
                taskRef:
                  name: git-clone
                matrix:
                  params:
                    - name: revision
                      value:
                      - "main"
                      - "test"
              - name: test-task
                taskRef:
                  name: test-runner
        """)
    return create_yaml_file(content)


class TestModTaskAddParamOperation:
    """Test cases for ModTaskAddParamOperation class."""

    def test_initialization(self):
        """Test operation initialization."""
        op = ModTaskAddParamOperation("clone", "timeout", "30m")
        assert op.task_name == "clone"
        assert op.param_name == "timeout"
        assert op.param_value == "30m"

    def test_add_param_to_existing_params_list(self, pipeline_yaml_file):
        """Test adding a parameter to a task that already has parameters."""
        op = ModTaskAddParamOperation("clone", "timeout", "30m")

        # Load initial data
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._do_action(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result is True

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
                    - name: url
                      value: "https://github.com/example/repo"
                    - name: revision
                      value: "main"
                    - name: timeout
                      value: 30m
                - name: build
                  taskRef:
                    name: buildah
                  params:
                    - name: IMAGE
                      value: "registry.io/app:latest"
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_yaml_file) == expected

    def test_add_param_to_task_without_params(self, pipeline_yaml_file):
        """Test adding a parameter to a task that has no existing parameters."""
        op = ModTaskAddParamOperation("test-task", "verbose", "true")

        # Load initial data
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._do_action(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result is True

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
                    - name: url
                      value: "https://github.com/example/repo"
                    - name: revision
                      value: "main"
                - name: build
                  taskRef:
                    name: buildah
                  params:
                    - name: IMAGE
                      value: "registry.io/app:latest"
                - name: test-task
                  taskRef:
                    name: test-runner
                  params:
                    - name: verbose
                      value: 'true'
            """)

        assert read_file_content(pipeline_yaml_file) == expected

    def test_update_existing_param_value(self, pipeline_yaml_file):
        """Test updating an existing parameter value."""
        op = ModTaskAddParamOperation("clone", "url", "https://github.com/new/repo")

        # Load initial data
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._do_action(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result is True

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
                    - name: url
                      value: https://github.com/new/repo
                    - name: revision
                      value: "main"
                - name: build
                  taskRef:
                    name: buildah
                  params:
                    - name: IMAGE
                      value: "registry.io/app:latest"
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_yaml_file) == expected

    def test_update_existing_param_value_with_array(self, pipeline_yaml_file):
        """Test updating an existing parameter value."""
        op = ModTaskAddParamOperation(
            "clone", "url", ["https://github.com/new/repo", "another_url"]
        )

        # Load initial data
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._do_action(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result is True

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
                    - name: url
                      value:
                        - https://github.com/new/repo
                        - another_url
                    - name: revision
                      value: "main"
                - name: build
                  taskRef:
                    name: buildah
                  params:
                    - name: IMAGE
                      value: "registry.io/app:latest"
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_yaml_file) == expected

    def test_no_change_when_param_value_same(self, pipeline_yaml_file):
        """Test that no change is made when parameter value is already the same."""
        op = ModTaskAddParamOperation("clone", "url", "https://github.com/example/repo")

        # Load initial data
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._do_action(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result is False  # No change needed

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
                    - name: url
                      value: "https://github.com/example/repo"
                    - name: revision
                      value: "main"
                - name: build
                  taskRef:
                    name: buildah
                  params:
                    - name: IMAGE
                      value: "registry.io/app:latest"
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_yaml_file) == expected

    def test_task_not_found(self, pipeline_yaml_file):
        """Test behavior when specified task doesn't exist."""
        op = ModTaskAddParamOperation("nonexistent-task", "param", "value")

        # Load initial data
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        with pytest.raises(TaskNotFoundError):
            op._do_action(tasks, ["spec", "tasks"], pipeline_yaml_file, style)

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
                    - name: url
                      value: "https://github.com/example/repo"
                    - name: revision
                      value: "main"
                - name: build
                  taskRef:
                    name: buildah
                  params:
                    - name: IMAGE
                      value: "registry.io/app:latest"
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_yaml_file) == expected

    def test_handle_pipeline_file(self, pipeline_yaml_file):
        """Test handle_pipeline_file method."""
        op = ModTaskAddParamOperation("clone", "timeout", "30m")

        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)

        # This should not raise an exception
        op.handle_pipeline_file(pipeline_yaml_file, loaded_doc, style)

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
                    - name: url
                      value: "https://github.com/example/repo"
                    - name: revision
                      value: "main"
                    - name: timeout
                      value: 30m
                - name: build
                  taskRef:
                    name: buildah
                  params:
                    - name: IMAGE
                      value: "registry.io/app:latest"
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_yaml_file) == expected

    def test_handle_pipeline_run_file(self, pipeline_run_yaml_file):
        """Test handle_pipeline_run_file method."""
        op = ModTaskAddParamOperation("clone", "timeout", "30m")

        loaded_doc = load_yaml(pipeline_run_yaml_file)
        style = YAMLStyle.detect(pipeline_run_yaml_file)

        # This should not raise an exception
        op.handle_pipeline_run_file(pipeline_run_yaml_file, loaded_doc, style)
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
                      - name: url
                        value: "https://github.com/example/repo"
                      - name: timeout
                        value: 30m
                  - name: build
                    taskRef:
                      name: buildah
                  - name: deploy
                    taskRef:
                      name: kubectl-deploy
                    params:
                      - name: image
                        value: "registry.io/app:latest"
                      - name: namespace
                        value: "production"
            """)

        assert read_file_content(pipeline_run_yaml_file) == expected

    def test_handle_pipeline_file_finally(self, pipeline_finally_yaml_file):
        """Test handle_pipeline_file method (with tasks in finally section)."""
        op = ModTaskAddParamOperation("clone", "timeout", "30m")

        loaded_doc = load_yaml(pipeline_finally_yaml_file)
        style = YAMLStyle.detect(pipeline_finally_yaml_file)

        # This should not raise an exception
        op.handle_pipeline_file(pipeline_finally_yaml_file, loaded_doc, style)

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              finally:
                - name: clone
                  taskRef:
                    name: git-clone
                  params:
                    - name: url
                      value: "https://github.com/example/repo"
                    - name: revision
                      value: "main"
                    - name: timeout
                      value: 30m
                - name: build
                  taskRef:
                    name: buildah
                  params:
                    - name: IMAGE
                      value: "registry.io/app:latest"
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_finally_yaml_file) == expected

    def test_handle_pipeline_run_file_finally(self, pipeline_run_finally_yaml_file):
        """Test handle_pipeline_run_file method (with tasks in finally section)."""
        op = ModTaskAddParamOperation("clone", "timeout", "30m")

        loaded_doc = load_yaml(pipeline_run_finally_yaml_file)
        style = YAMLStyle.detect(pipeline_run_finally_yaml_file)

        # This should not raise an exception
        op.handle_pipeline_run_file(pipeline_run_finally_yaml_file, loaded_doc, style)

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: PipelineRun
            metadata:
              name: test-pipeline-run
            spec:
              pipelineSpec:
                finally:
                  - name: clone
                    taskRef:
                      name: git-clone
                    params:
                      - name: url
                        value: "https://github.com/example/repo"
                      - name: timeout
                        value: 30m
                  - name: build
                    taskRef:
                      name: buildah
                  - name: deploy
                    taskRef:
                      name: kubectl-deploy
                    params:
                      - name: image
                        value: "registry.io/app:latest"
                      - name: namespace
                        value: "production"
            """)

        assert read_file_content(pipeline_run_finally_yaml_file) == expected


class TestModTaskRemoveParamOperation:
    """Test cases for ModTaskRemoveParamOperation class."""

    def test_initialization(self):
        """Test operation initialization."""
        op = ModTaskRemoveParamOperation("clone", "timeout")
        assert op.task_name == "clone"
        assert op.param_name == "timeout"

    def test_remove_existing_param(self, pipeline_yaml_file):
        """Test removing an existing parameter."""
        op = ModTaskRemoveParamOperation("clone", "url")

        # Load initial data
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._do_action(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result is True

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
                    - name: revision
                      value: "main"
                - name: build
                  taskRef:
                    name: buildah
                  params:
                    - name: IMAGE
                      value: "registry.io/app:latest"
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_yaml_file) == expected

    def test_remove_param_from_task_without_params(self, pipeline_yaml_file):
        """Test removing a parameter from a task that has no parameters."""
        op = ModTaskRemoveParamOperation("test-task", "nonexistent")

        # Load initial data
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._do_action(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result is False

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
                    - name: url
                      value: "https://github.com/example/repo"
                    - name: revision
                      value: "main"
                - name: build
                  taskRef:
                    name: buildah
                  params:
                    - name: IMAGE
                      value: "registry.io/app:latest"
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_yaml_file) == expected

    def test_remove_nonexistent_param(self, pipeline_yaml_file):
        """Test removing a parameter that doesn't exist."""
        op = ModTaskRemoveParamOperation("clone", "nonexistent-param")

        # Load initial data
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._do_action(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result is False

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
                    - name: url
                      value: "https://github.com/example/repo"
                    - name: revision
                      value: "main"
                - name: build
                  taskRef:
                    name: buildah
                  params:
                    - name: IMAGE
                      value: "registry.io/app:latest"
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_yaml_file) == expected

    def test_task_not_found(self, pipeline_yaml_file):
        """Test behavior when specified task doesn't exist."""
        op = ModTaskRemoveParamOperation("nonexistent-task", "param")

        # Load initial data
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        with pytest.raises(TaskNotFoundError):
            op._do_action(tasks, ["spec", "tasks"], pipeline_yaml_file, style)

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
                    - name: url
                      value: "https://github.com/example/repo"
                    - name: revision
                      value: "main"
                - name: build
                  taskRef:
                    name: buildah
                  params:
                    - name: IMAGE
                      value: "registry.io/app:latest"
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_yaml_file) == expected

    def test_handle_pipeline_file(self, pipeline_yaml_file):
        """Test handle_pipeline_file method."""
        op = ModTaskRemoveParamOperation("clone", "url")

        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)

        # This should not raise an exception
        op.handle_pipeline_file(pipeline_yaml_file, loaded_doc, style)

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
                    - name: revision
                      value: "main"
                - name: build
                  taskRef:
                    name: buildah
                  params:
                    - name: IMAGE
                      value: "registry.io/app:latest"
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_yaml_file) == expected

    def test_handle_pipeline_run_file(self, pipeline_run_yaml_file):
        """Test handle_pipeline_run_file method."""
        op = ModTaskRemoveParamOperation("deploy", "namespace")

        loaded_doc = load_yaml(pipeline_run_yaml_file)
        style = YAMLStyle.detect(pipeline_run_yaml_file)

        # This should not raise an exception
        op.handle_pipeline_run_file(pipeline_run_yaml_file, loaded_doc, style)

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
                      - name: url
                        value: "https://github.com/example/repo"
                  - name: build
                    taskRef:
                      name: buildah
                  - name: deploy
                    taskRef:
                      name: kubectl-deploy
                    params:
                      - name: image
                        value: "registry.io/app:latest"
            """)

        assert read_file_content(pipeline_run_yaml_file) == expected

    def test_handle_pipeline_file_finally(self, pipeline_finally_yaml_file):
        """Test handle_pipeline_file method (with tasks in finally section).."""
        op = ModTaskRemoveParamOperation("clone", "url")

        loaded_doc = load_yaml(pipeline_finally_yaml_file)
        style = YAMLStyle.detect(pipeline_finally_yaml_file)

        # This should not raise an exception
        op.handle_pipeline_file(pipeline_finally_yaml_file, loaded_doc, style)

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              finally:
                - name: clone
                  taskRef:
                    name: git-clone
                  params:
                    - name: revision
                      value: "main"
                - name: build
                  taskRef:
                    name: buildah
                  params:
                    - name: IMAGE
                      value: "registry.io/app:latest"
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_finally_yaml_file) == expected

    def test_handle_pipeline_run_file_finally(self, pipeline_run_finally_yaml_file):
        """Test handle_pipeline_run_file method (with tasks in finally section).."""
        op = ModTaskRemoveParamOperation("deploy", "namespace")

        loaded_doc = load_yaml(pipeline_run_finally_yaml_file)
        style = YAMLStyle.detect(pipeline_run_finally_yaml_file)

        # This should not raise an exception
        op.handle_pipeline_run_file(pipeline_run_finally_yaml_file, loaded_doc, style)

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: PipelineRun
            metadata:
              name: test-pipeline-run
            spec:
              pipelineSpec:
                finally:
                  - name: clone
                    taskRef:
                      name: git-clone
                    params:
                      - name: url
                        value: "https://github.com/example/repo"
                  - name: build
                    taskRef:
                      name: buildah
                  - name: deploy
                    taskRef:
                      name: kubectl-deploy
                    params:
                      - name: image
                        value: "registry.io/app:latest"
            """)

        assert read_file_content(pipeline_run_finally_yaml_file) == expected


class TestModTaskMatrixAddParamOperation:
    """Test cases for ModTaskAddParamOperation class."""

    def test_initialization(self):
        """Test operation initialization."""
        op = ModTaskMatrixAddParamOperation("clone", "timeout", "30m")
        assert op.task_name == "clone"
        assert op.param_name == "timeout"
        assert op.param_value == "30m"

    def test_add_param_to_existing_params_list(self, pipeline_matrix_yaml_file):
        """Test adding a parameter to a task that already has parameters."""
        op = ModTaskMatrixAddParamOperation("clone", "timeout", "30m")

        # Load initial data
        loaded_doc = load_yaml(pipeline_matrix_yaml_file)
        style = YAMLStyle.detect(pipeline_matrix_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._do_action(tasks, ["spec", "tasks"], pipeline_matrix_yaml_file, style)
        assert result is True

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
                  matrix:
                    params:
                      - name: revision
                        value:
                        - "main"
                        - "test"
                      - name: timeout
                        value: 30m
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_matrix_yaml_file) == expected

    def test_add_param_to_task_without_params(self, pipeline_matrix_yaml_file):
        """Test adding a parameter to a task that has no existing parameters."""
        op = ModTaskMatrixAddParamOperation("test-task", "verbose", "true")

        # Load initial data
        loaded_doc = load_yaml(pipeline_matrix_yaml_file)
        style = YAMLStyle.detect(pipeline_matrix_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._do_action(tasks, ["spec", "tasks"], pipeline_matrix_yaml_file, style)
        assert result is True

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
                  matrix:
                    params:
                      - name: revision
                        value:
                        - "main"
                        - "test"
                - name: test-task
                  taskRef:
                    name: test-runner
                  matrix:
                    params:
                    - name: verbose
                      value: 'true'
            """)

        assert read_file_content(pipeline_matrix_yaml_file) == expected

    def test_update_existing_param_value(self, pipeline_matrix_yaml_file):
        """Test updating an existing parameter value."""
        op = ModTaskMatrixAddParamOperation("clone", "revision", "test-scalar")

        # Load initial data
        loaded_doc = load_yaml(pipeline_matrix_yaml_file)
        style = YAMLStyle.detect(pipeline_matrix_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._do_action(tasks, ["spec", "tasks"], pipeline_matrix_yaml_file, style)
        assert result is True

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
                  matrix:
                    params:
                      - name: revision
                        value: test-scalar
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_matrix_yaml_file) == expected

    def test_update_existing_param_value_with_array(self, pipeline_matrix_yaml_file):
        """Test updating an existing parameter value."""
        op = ModTaskMatrixAddParamOperation("clone", "revision", ["test1", "test2"])

        # Load initial data
        loaded_doc = load_yaml(pipeline_matrix_yaml_file)
        style = YAMLStyle.detect(pipeline_matrix_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._do_action(tasks, ["spec", "tasks"], pipeline_matrix_yaml_file, style)
        assert result is True

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
                  matrix:
                    params:
                      - name: revision
                        value:
                        - test1
                        - test2
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_matrix_yaml_file) == expected

    def test_no_change_when_param_value_same(self, pipeline_matrix_yaml_file):
        """Test that no change is made when parameter value is already the same."""
        op = ModTaskMatrixAddParamOperation("clone", "revision", ["main", "test"])

        # Load initial data
        loaded_doc = load_yaml(pipeline_matrix_yaml_file)
        style = YAMLStyle.detect(pipeline_matrix_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._do_action(tasks, ["spec", "tasks"], pipeline_matrix_yaml_file, style)
        assert result is False  # No change needed

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
                  matrix:
                    params:
                      - name: revision
                        value:
                        - "main"
                        - "test"
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_matrix_yaml_file) == expected

    def test_task_not_found(self, pipeline_matrix_yaml_file):
        """Test behavior when specified task doesn't exist."""
        op = ModTaskMatrixAddParamOperation("nonexistent-task", "param", "value")

        # Load initial data
        loaded_doc = load_yaml(pipeline_matrix_yaml_file)
        style = YAMLStyle.detect(pipeline_matrix_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        with pytest.raises(TaskNotFoundError):
            op._do_action(tasks, ["spec", "tasks"], pipeline_matrix_yaml_file, style)

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
                  matrix:
                    params:
                      - name: revision
                        value:
                        - "main"
                        - "test"
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_matrix_yaml_file) == expected

    def test_handle_pipeline_file(self, pipeline_matrix_yaml_file):
        """Test handle_pipeline_file method."""
        op = ModTaskMatrixAddParamOperation("clone", "timeout", "30m")

        loaded_doc = load_yaml(pipeline_matrix_yaml_file)
        style = YAMLStyle.detect(pipeline_matrix_yaml_file)

        # This should not raise an exception
        op.handle_pipeline_file(pipeline_matrix_yaml_file, loaded_doc, style)

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
                  matrix:
                    params:
                      - name: revision
                        value:
                        - "main"
                        - "test"
                      - name: timeout
                        value: 30m
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_matrix_yaml_file) == expected

    def test_handle_pipeline_run_file(self, pipeline_run_matrix_yaml_file):
        """Test handle_pipeline_run_file method."""
        op = ModTaskMatrixAddParamOperation("clone", "timeout", "30m")

        loaded_doc = load_yaml(pipeline_run_matrix_yaml_file)
        style = YAMLStyle.detect(pipeline_run_matrix_yaml_file)

        # This should not raise an exception
        op.handle_pipeline_run_file(pipeline_run_matrix_yaml_file, loaded_doc, style)
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
                    matrix:
                      params:
                        - name: revision
                          value:
                          - "main"
                          - "test"
                        - name: timeout
                          value: 30m
                  - name: test-task
                    taskRef:
                      name: test-runner
            """)

        assert read_file_content(pipeline_run_matrix_yaml_file) == expected

    def test_handle_pipeline_file_finally(self, pipeline_matrix_finally_yaml_file):
        """Test handle_pipeline_file method (with tasks in finally section)."""
        op = ModTaskMatrixAddParamOperation("clone", "timeout", "30m")

        loaded_doc = load_yaml(pipeline_matrix_finally_yaml_file)
        style = YAMLStyle.detect(pipeline_matrix_finally_yaml_file)

        # This should not raise an exception
        op.handle_pipeline_file(pipeline_matrix_finally_yaml_file, loaded_doc, style)

        expected = dedent("""\
        apiVersion: tekton.dev/v1
        kind: Pipeline
        metadata:
          name: test-pipeline
        spec:
          finally:
            - name: clone
              taskRef:
                name: git-clone
              matrix:
                params:
                  - name: revision
                    value:
                    - "main"
                    - "test"
                  - name: timeout
                    value: 30m
            - name: test-task
              taskRef:
                name: test-runner
            """)

        assert read_file_content(pipeline_matrix_finally_yaml_file) == expected

    def test_handle_pipeline_run_file_finally(self, pipeline_run_matrix_finally_yaml_file):
        """Test handle_pipeline_run_file method (with tasks in finally section)."""
        op = ModTaskMatrixAddParamOperation("clone", "timeout", "30m")

        loaded_doc = load_yaml(pipeline_run_matrix_finally_yaml_file)
        style = YAMLStyle.detect(pipeline_run_matrix_finally_yaml_file)

        # This should not raise an exception
        op.handle_pipeline_run_file(pipeline_run_matrix_finally_yaml_file, loaded_doc, style)

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: PipelineRun
            metadata:
              name: test-pipeline-run
            spec:
              pipelineSpec:
                finally:
                  - name: clone
                    taskRef:
                      name: git-clone
                    matrix:
                      params:
                        - name: revision
                          value:
                          - "main"
                          - "test"
                        - name: timeout
                          value: 30m
                  - name: test-task
                    taskRef:
                      name: test-runner
            """)

        assert read_file_content(pipeline_run_matrix_finally_yaml_file) == expected

    def test_handle_pipeline_run_file_matrix_include_only(
        self, pipeline_run_matrix_include_only_yaml_file
    ):
        """Test when matrix has defined include attr."""
        op = ModTaskMatrixAddParamOperation("clone", "timeout", "30m")

        loaded_doc = load_yaml(pipeline_run_matrix_include_only_yaml_file)
        style = YAMLStyle.detect(pipeline_run_matrix_include_only_yaml_file)

        # This should not raise an exception
        op.handle_pipeline_run_file(pipeline_run_matrix_include_only_yaml_file, loaded_doc, style)

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
                matrix:
                  include:
                    - name: test-one
                      params:
                      - name: url
                        value: $(params.url)
                  params:
                  - name: timeout
                    value: 30m
              - name: test-task
                taskRef:
                  name: test-runner
            """)

        assert read_file_content(pipeline_run_matrix_include_only_yaml_file) == expected


class TestModTaskMatrixRemoveParamOperation:
    """Test cases for ModTaskRemoveParamOperation class."""

    def test_initialization(self):
        """Test operation initialization."""
        op = ModTaskMatrixRemoveParamOperation("clone", "timeout")
        assert op.task_name == "clone"
        assert op.param_name == "timeout"

    def test_remove_existing_param(self, pipeline_matrix_yaml_file):
        """Test removing an existing parameter."""
        op = ModTaskMatrixRemoveParamOperation("clone", "revision")

        # Load initial data
        loaded_doc = load_yaml(pipeline_matrix_yaml_file)
        style = YAMLStyle.detect(pipeline_matrix_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._do_action(tasks, ["spec", "tasks"], pipeline_matrix_yaml_file, style)
        assert result is True

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
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_matrix_yaml_file) == expected

    def test_remove_param_from_task_without_params(self, pipeline_matrix_yaml_file):
        """Test removing a parameter from a task that has no parameters."""
        op = ModTaskMatrixRemoveParamOperation("test-task", "nonexistent")

        # Load initial data
        loaded_doc = load_yaml(pipeline_matrix_yaml_file)
        style = YAMLStyle.detect(pipeline_matrix_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._do_action(tasks, ["spec", "tasks"], pipeline_matrix_yaml_file, style)
        assert result is False

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
                  matrix:
                    params:
                      - name: revision
                        value:
                        - "main"
                        - "test"
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_matrix_yaml_file) == expected

    def test_remove_nonexistent_param(self, pipeline_matrix_yaml_file):
        """Test removing a parameter that doesn't exist."""
        op = ModTaskMatrixRemoveParamOperation("clone", "nonexistent-param")

        # Load initial data
        loaded_doc = load_yaml(pipeline_matrix_yaml_file)
        style = YAMLStyle.detect(pipeline_matrix_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._do_action(tasks, ["spec", "tasks"], pipeline_matrix_yaml_file, style)
        assert result is False

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
                  matrix:
                    params:
                      - name: revision
                        value:
                        - "main"
                        - "test"
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_matrix_yaml_file) == expected

    def test_task_not_found(self, pipeline_matrix_yaml_file):
        """Test behavior when specified task doesn't exist."""
        op = ModTaskMatrixRemoveParamOperation("nonexistent-task", "param")

        # Load initial data
        loaded_doc = load_yaml(pipeline_matrix_yaml_file)
        style = YAMLStyle.detect(pipeline_matrix_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        with pytest.raises(TaskNotFoundError):
            op._do_action(tasks, ["spec", "tasks"], pipeline_matrix_yaml_file, style)

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
                  matrix:
                    params:
                      - name: revision
                        value:
                        - "main"
                        - "test"
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_matrix_yaml_file) == expected

    def test_handle_pipeline_file(self, pipeline_matrix_yaml_file):
        """Test handle_pipeline_file method."""
        op = ModTaskMatrixRemoveParamOperation("clone", "revision")

        loaded_doc = load_yaml(pipeline_matrix_yaml_file)
        style = YAMLStyle.detect(pipeline_matrix_yaml_file)

        # This should not raise an exception
        op.handle_pipeline_file(pipeline_matrix_yaml_file, loaded_doc, style)

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
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_matrix_yaml_file) == expected

    def test_handle_pipeline_run_file(self, pipeline_run_matrix_yaml_file):
        """Test handle_pipeline_run_file method."""
        op = ModTaskMatrixRemoveParamOperation("clone", "revision")

        loaded_doc = load_yaml(pipeline_run_matrix_yaml_file)
        style = YAMLStyle.detect(pipeline_run_matrix_yaml_file)

        # This should not raise an exception
        op.handle_pipeline_run_file(pipeline_run_matrix_yaml_file, loaded_doc, style)

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
                  - name: test-task
                    taskRef:
                      name: test-runner
            """)

        assert read_file_content(pipeline_run_matrix_yaml_file) == expected

    def test_handle_pipeline_file_finally(self, pipeline_matrix_finally_yaml_file):
        """Test handle_pipeline_file method (with tasks in finally section).."""
        op = ModTaskMatrixRemoveParamOperation("clone", "revision")

        loaded_doc = load_yaml(pipeline_matrix_finally_yaml_file)
        style = YAMLStyle.detect(pipeline_matrix_finally_yaml_file)

        # This should not raise an exception
        op.handle_pipeline_file(pipeline_matrix_finally_yaml_file, loaded_doc, style)

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              finally:
                - name: clone
                  taskRef:
                    name: git-clone
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_matrix_finally_yaml_file) == expected

    def test_handle_pipeline_run_file_finally(self, pipeline_run_matrix_finally_yaml_file):
        """Test handle_pipeline_run_file method (with tasks in finally section).."""
        op = ModTaskMatrixRemoveParamOperation("clone", "revision")

        loaded_doc = load_yaml(pipeline_run_matrix_finally_yaml_file)
        style = YAMLStyle.detect(pipeline_run_matrix_finally_yaml_file)

        # This should not raise an exception
        op.handle_pipeline_run_file(pipeline_run_matrix_finally_yaml_file, loaded_doc, style)

        expected = dedent("""\
            apiVersion: tekton.dev/v1
            kind: PipelineRun
            metadata:
              name: test-pipeline-run
            spec:
              pipelineSpec:
                finally:
                  - name: clone
                    taskRef:
                      name: git-clone
                  - name: test-task
                    taskRef:
                      name: test-runner
            """)

        assert read_file_content(pipeline_run_matrix_finally_yaml_file) == expected

    def test_handle_pipeline_run_file_matrix_include_only(
        self, pipeline_run_matrix_include_only_yaml_file
    ):
        """Test removal of nonexistent params entry, but with defined matrix"""
        op = ModTaskMatrixRemoveParamOperation("clone", "revision")

        loaded_doc = load_yaml(pipeline_run_matrix_include_only_yaml_file)
        style = YAMLStyle.detect(pipeline_run_matrix_include_only_yaml_file)

        # This should not raise an exception
        op.handle_pipeline_run_file(pipeline_run_matrix_include_only_yaml_file, loaded_doc, style)

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
                    matrix:
                      include:
                        - name: test-one
                          params:
                          - name: url
                            value: $(params.url)
                  - name: test-task
                    taskRef:
                      name: test-runner
            """)

        assert read_file_content(pipeline_run_matrix_include_only_yaml_file) == expected


@pytest.fixture
def pipeline_bundles_yaml_file(create_yaml_file):
    """Pipeline YAML with a bundles-resolver taskRef, used for rename tests."""
    content = dedent("""\
        apiVersion: tekton.dev/v1
        kind: Pipeline
        metadata:
          name: test-pipeline
        spec:
          tasks:
            - name: clair-scan
              taskRef:
                resolver: bundles
                params:
                  - name: name
                    value: task-clair-scan
                  - name: bundle
                    value: quay.io/org/task-clair-scan:0.1@sha256:abc123
                  - name: kind
                    value: task
              params:
                - name: image-url
                  value: $(tasks.build.results.IMAGE_URL)
            - name: build
              taskRef:
                name: buildah
        """)
    return create_yaml_file(content)


@pytest.fixture
def pipeline_run_bundles_yaml_file(create_yaml_file):
    """PipelineRun YAML with a bundles-resolver taskRef, used for rename tests."""
    content = dedent("""\
        apiVersion: tekton.dev/v1
        kind: PipelineRun
        metadata:
          name: test-pipeline-run
        spec:
          pipelineSpec:
            tasks:
              - name: clair-scan
                taskRef:
                  resolver: bundles
                  params:
                    - name: name
                      value: task-clair-scan
                    - name: bundle
                      value: quay.io/org/task-clair-scan:0.1@sha256:abc123
                    - name: kind
                      value: task
                params:
                  - name: image-url
                    value: $(tasks.build.results.IMAGE_URL)
              - name: build
                taskRef:
                  name: buildah
        """)
    return create_yaml_file(content)


class TestModTaskRenameOperation:
    """Test cases for ModTaskRenameOperation."""

    def test_initialization(self):
        op = ModTaskRenameOperation("clair-scan", "roxctl-scan")
        assert op.task_name == "clair-scan"
        assert op.new_name == "roxctl-scan"
        assert op.task_ref_name is None

    def test_initialization_with_task_ref_name(self):
        op = ModTaskRenameOperation("clair-scan", "roxctl-scan", "task-roxctl-scan")
        assert op.task_ref_name == "task-roxctl-scan"

    def test_rename_task_name(self, pipeline_yaml_file):
        op = ModTaskRenameOperation("clone", "new-clone")

        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        result = op._do_action(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result is True

        doc = load_yaml(pipeline_yaml_file)
        task_names = [t["name"] for t in doc["spec"]["tasks"]]
        assert "new-clone" in task_names
        assert "clone" not in task_names

    def test_rename_does_not_affect_other_tasks(self, pipeline_yaml_file):
        op = ModTaskRenameOperation("clone", "new-clone")

        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        op._do_action(tasks, ["spec", "tasks"], pipeline_yaml_file, style)

        doc = load_yaml(pipeline_yaml_file)
        task_names = [t["name"] for t in doc["spec"]["tasks"]]
        assert "build" in task_names
        assert "test-task" in task_names

    def test_rename_with_task_ref_name(self, pipeline_bundles_yaml_file):
        op = ModTaskRenameOperation("clair-scan", "roxctl-scan", "task-roxctl-scan")

        loaded_doc = load_yaml(pipeline_bundles_yaml_file)
        style = YAMLStyle.detect(pipeline_bundles_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        result = op._do_action(tasks, ["spec", "tasks"], pipeline_bundles_yaml_file, style)
        assert result is True

        doc = load_yaml(pipeline_bundles_yaml_file)
        task_names = [t["name"] for t in doc["spec"]["tasks"]]
        assert "roxctl-scan" in task_names
        assert "clair-scan" not in task_names

        new_task = next(t for t in doc["spec"]["tasks"] if t["name"] == "roxctl-scan")
        taskref_params = new_task["taskRef"]["params"]
        name_param = next(p for p in taskref_params if p["name"] == "name")
        assert name_param["value"] == "task-roxctl-scan"

    def test_task_ref_name_skipped_when_no_taskref_params(self, pipeline_yaml_file):
        """When taskRef has no params (non-bundles style), --task-ref-name is a no-error no-op."""
        op = ModTaskRenameOperation("clone", "new-clone", "task-new-clone")

        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        result = op._do_action(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result is True

        doc = load_yaml(pipeline_yaml_file)
        task_names = [t["name"] for t in doc["spec"]["tasks"]]
        assert "new-clone" in task_names

    def test_task_not_found(self, pipeline_yaml_file):
        op = ModTaskRenameOperation("nonexistent", "something-else")

        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        with pytest.raises(TaskNotFoundError):
            op._do_action(tasks, ["spec", "tasks"], pipeline_yaml_file, style)

        doc = load_yaml(pipeline_yaml_file)
        task_names = [t["name"] for t in doc["spec"]["tasks"]]
        assert task_names == ["clone", "build", "test-task"]

    def test_handle_pipeline_file(self, pipeline_bundles_yaml_file):
        op = ModTaskRenameOperation("clair-scan", "roxctl-scan", "task-roxctl-scan")

        loaded_doc = load_yaml(pipeline_bundles_yaml_file)
        style = YAMLStyle.detect(pipeline_bundles_yaml_file)

        op.handle_pipeline_file(pipeline_bundles_yaml_file, loaded_doc, style)

        doc = load_yaml(pipeline_bundles_yaml_file)
        tasks = doc["spec"]["tasks"]
        assert tasks[0]["name"] == "roxctl-scan"
        name_param = next(p for p in tasks[0]["taskRef"]["params"] if p["name"] == "name")
        assert name_param["value"] == "task-roxctl-scan"

    def test_handle_pipeline_run_file(self, pipeline_run_bundles_yaml_file):
        op = ModTaskRenameOperation("clair-scan", "roxctl-scan", "task-roxctl-scan")

        loaded_doc = load_yaml(pipeline_run_bundles_yaml_file)
        style = YAMLStyle.detect(pipeline_run_bundles_yaml_file)

        op.handle_pipeline_run_file(pipeline_run_bundles_yaml_file, loaded_doc, style)

        doc = load_yaml(pipeline_run_bundles_yaml_file)
        tasks = doc["spec"]["pipelineSpec"]["tasks"]
        assert tasks[0]["name"] == "roxctl-scan"
        name_param = next(p for p in tasks[0]["taskRef"]["params"] if p["name"] == "name")
        assert name_param["value"] == "task-roxctl-scan"

    def test_handle_pipeline_file_finally(self, create_yaml_file):
        content = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              finally:
                - name: clair-scan
                  taskRef:
                    resolver: bundles
                    params:
                      - name: name
                        value: task-clair-scan
                      - name: bundle
                        value: quay.io/org/task-clair-scan:0.1@sha256:abc123
                      - name: kind
                        value: task
            """)
        pipeline_file = create_yaml_file(content)
        op = ModTaskRenameOperation("clair-scan", "roxctl-scan", "task-roxctl-scan")

        loaded_doc = load_yaml(pipeline_file)
        style = YAMLStyle.detect(pipeline_file)

        op.handle_pipeline_file(pipeline_file, loaded_doc, style)

        doc = load_yaml(pipeline_file)
        tasks = doc["spec"]["finally"]
        assert tasks[0]["name"] == "roxctl-scan"
        name_param = next(p for p in tasks[0]["taskRef"]["params"] if p["name"] == "name")
        assert name_param["value"] == "task-roxctl-scan"

    def test_duplicate_name_raises_error(self, create_yaml_file):
        """Renaming to a name already used by another task must raise DuplicateTaskNameError."""
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
                - name: build
                  taskRef:
                    name: buildah
            """)
        pipeline_file = create_yaml_file(content)
        op = ModTaskRenameOperation("clone", "build")

        loaded_doc = load_yaml(pipeline_file)
        style = YAMLStyle.detect(pipeline_file)

        with pytest.raises(DuplicateTaskNameError, match="'build' already exists"):
            op.handle_pipeline_file(pipeline_file, loaded_doc, style)

        # File must be unchanged
        doc = load_yaml(pipeline_file)
        task_names = [t["name"] for t in doc["spec"]["tasks"]]
        assert task_names == ["clone", "build"]

    def test_duplicate_name_across_tasks_and_finally(self, create_yaml_file):
        """Renaming a tasks-section task to a name used in finally must fail."""
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
              finally:
                - name: notify
                  taskRef:
                    name: slack-notify
            """)
        pipeline_file = create_yaml_file(content)
        op = ModTaskRenameOperation("clone", "notify")

        loaded_doc = load_yaml(pipeline_file)
        style = YAMLStyle.detect(pipeline_file)

        with pytest.raises(DuplicateTaskNameError):
            op.handle_pipeline_file(pipeline_file, loaded_doc, style)

    def test_run_after_updated_on_rename(self, create_yaml_file):
        """runAfter references to the renamed task are updated in other tasks."""
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
                - name: build
                  taskRef:
                    name: buildah
                  runAfter:
                    - clone
                - name: test-task
                  taskRef:
                    name: test-runner
                  runAfter:
                    - clone
                    - build
            """)
        pipeline_file = create_yaml_file(content)
        op = ModTaskRenameOperation("clone", "git-clone-task")

        loaded_doc = load_yaml(pipeline_file)
        style = YAMLStyle.detect(pipeline_file)
        op.handle_pipeline_file(pipeline_file, loaded_doc, style)

        doc = load_yaml(pipeline_file)
        tasks = {t["name"]: t for t in doc["spec"]["tasks"]}
        assert "git-clone-task" in tasks
        assert "clone" not in tasks
        assert tasks["build"]["runAfter"] == ["git-clone-task"]
        assert tasks["test-task"]["runAfter"] == ["git-clone-task", "build"]

    def test_run_after_updated_in_finally_tasks(self, create_yaml_file):
        """runAfter in finally tasks referencing the renamed task are also updated."""
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
                - name: build
                  taskRef:
                    name: buildah
                  runAfter:
                    - clone
              finally:
                - name: notify
                  taskRef:
                    name: slack-notify
                  runAfter:
                    - clone
            """)
        pipeline_file = create_yaml_file(content)
        op = ModTaskRenameOperation("clone", "git-clone-task")

        loaded_doc = load_yaml(pipeline_file)
        style = YAMLStyle.detect(pipeline_file)
        op.handle_pipeline_file(pipeline_file, loaded_doc, style)

        doc = load_yaml(pipeline_file)
        tasks = {t["name"]: t for t in doc["spec"]["tasks"]}
        finally_tasks = {t["name"]: t for t in doc["spec"]["finally"]}
        assert "git-clone-task" in tasks
        assert tasks["build"]["runAfter"] == ["git-clone-task"]
        assert finally_tasks["notify"]["runAfter"] == ["git-clone-task"]

    def test_run_after_updated_in_pipeline_run(self, create_yaml_file):
        """runAfter references are updated in PipelineRun files too."""
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
                  - name: build
                    taskRef:
                      name: buildah
                    runAfter:
                      - clone
            """)
        pipeline_file = create_yaml_file(content)
        op = ModTaskRenameOperation("clone", "git-clone-task")

        loaded_doc = load_yaml(pipeline_file)
        style = YAMLStyle.detect(pipeline_file)
        op.handle_pipeline_run_file(pipeline_file, loaded_doc, style)

        doc = load_yaml(pipeline_file)
        tasks = {t["name"]: t for t in doc["spec"]["pipelineSpec"]["tasks"]}
        assert "git-clone-task" in tasks
        assert tasks["build"]["runAfter"] == ["git-clone-task"]

    def test_no_run_after_refs_is_noop(self, pipeline_bundles_yaml_file):
        """When no tasks reference the renamed task in runAfter, the rename still works."""
        op = ModTaskRenameOperation("clair-scan", "roxctl-scan")

        loaded_doc = load_yaml(pipeline_bundles_yaml_file)
        style = YAMLStyle.detect(pipeline_bundles_yaml_file)
        op.handle_pipeline_file(pipeline_bundles_yaml_file, loaded_doc, style)

        doc = load_yaml(pipeline_bundles_yaml_file)
        task_names = [t["name"] for t in doc["spec"]["tasks"]]
        assert "roxctl-scan" in task_names
        assert "clair-scan" not in task_names


class TestModTaskSetBundleOperation:
    """Test cases for ModTaskSetBundleOperation."""

    NEW_BUNDLE = "quay.io/org/task-clair-scan:0.2@sha256:def456"

    def test_initialization(self):
        op = ModTaskSetBundleOperation("clair-scan", self.NEW_BUNDLE)
        assert op.task_name == "clair-scan"
        assert op.bundle_ref == self.NEW_BUNDLE
        assert op.task_ref_name is None

    def test_initialization_with_task_ref_name(self):
        op = ModTaskSetBundleOperation("clair-scan", self.NEW_BUNDLE, "task-clair-scan-v2")
        assert op.task_ref_name == "task-clair-scan-v2"

    def test_set_bundle(self, pipeline_bundles_yaml_file):
        op = ModTaskSetBundleOperation("clair-scan", self.NEW_BUNDLE)

        loaded_doc = load_yaml(pipeline_bundles_yaml_file)
        style = YAMLStyle.detect(pipeline_bundles_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        result = op._do_action(tasks, ["spec", "tasks"], pipeline_bundles_yaml_file, style)
        assert result is True

        doc = load_yaml(pipeline_bundles_yaml_file)
        task = next(t for t in doc["spec"]["tasks"] if t["name"] == "clair-scan")
        bundle_param = next(p for p in task["taskRef"]["params"] if p["name"] == "bundle")
        assert bundle_param["value"] == self.NEW_BUNDLE

    def test_set_bundle_already_set(self, pipeline_bundles_yaml_file):
        """Returns True without modifying the file when bundle is already the target value."""
        current_bundle = "quay.io/org/task-clair-scan:0.1@sha256:abc123"
        op = ModTaskSetBundleOperation("clair-scan", current_bundle)

        loaded_doc = load_yaml(pipeline_bundles_yaml_file)
        style = YAMLStyle.detect(pipeline_bundles_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        original_content = read_file_content(pipeline_bundles_yaml_file)
        result = op._do_action(tasks, ["spec", "tasks"], pipeline_bundles_yaml_file, style)
        assert result is True
        assert read_file_content(pipeline_bundles_yaml_file) == original_content

    def test_set_bundle_with_task_ref_name(self, pipeline_bundles_yaml_file):
        """Updates both the bundle and the taskRef name param when task_ref_name is given."""
        op = ModTaskSetBundleOperation("clair-scan", self.NEW_BUNDLE, "task-clair-scan-v2")

        loaded_doc = load_yaml(pipeline_bundles_yaml_file)
        style = YAMLStyle.detect(pipeline_bundles_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        result = op._do_action(tasks, ["spec", "tasks"], pipeline_bundles_yaml_file, style)
        assert result is True

        doc = load_yaml(pipeline_bundles_yaml_file)
        task = next(t for t in doc["spec"]["tasks"] if t["name"] == "clair-scan")
        ref_params = task["taskRef"]["params"]
        bundle_param = next(p for p in ref_params if p["name"] == "bundle")
        name_param = next(p for p in ref_params if p["name"] == "name")
        assert bundle_param["value"] == self.NEW_BUNDLE
        assert name_param["value"] == "task-clair-scan-v2"

    def test_task_without_taskref_params_returns_false(self, pipeline_yaml_file):
        """Returns False when the task's taskRef has no params (non-bundles resolver style)."""
        op = ModTaskSetBundleOperation("clone", self.NEW_BUNDLE)

        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        result = op._do_action(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result is False

    def test_task_without_bundle_param_returns_false(self, create_yaml_file):
        """Returns False when taskRef has params but none named 'bundle'."""
        content = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              tasks:
                - name: clair-scan
                  taskRef:
                    resolver: bundles
                    params:
                      - name: name
                        value: task-clair-scan
                      - name: kind
                        value: task
            """)
        pipeline_file = create_yaml_file(content)
        op = ModTaskSetBundleOperation("clair-scan", self.NEW_BUNDLE)

        loaded_doc = load_yaml(pipeline_file)
        style = YAMLStyle.detect(pipeline_file)
        tasks = loaded_doc["spec"]["tasks"]

        result = op._do_action(tasks, ["spec", "tasks"], pipeline_file, style)
        assert result is False

    def test_task_ref_name_skipped_when_no_name_param(self, create_yaml_file):
        """Warns and skips the name update when taskRef has no 'name' param."""
        content = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              tasks:
                - name: clair-scan
                  taskRef:
                    resolver: bundles
                    params:
                      - name: bundle
                        value: quay.io/org/task-clair-scan:0.1@sha256:abc123
                      - name: kind
                        value: task
            """)
        pipeline_file = create_yaml_file(content)
        op = ModTaskSetBundleOperation("clair-scan", self.NEW_BUNDLE, "task-clair-scan-v2")

        loaded_doc = load_yaml(pipeline_file)
        style = YAMLStyle.detect(pipeline_file)
        tasks = loaded_doc["spec"]["tasks"]

        result = op._do_action(tasks, ["spec", "tasks"], pipeline_file, style)
        assert result is True

        doc = load_yaml(pipeline_file)
        task = next(t for t in doc["spec"]["tasks"] if t["name"] == "clair-scan")
        bundle_param = next(p for p in task["taskRef"]["params"] if p["name"] == "bundle")
        assert bundle_param["value"] == self.NEW_BUNDLE

    def test_task_not_found_raises(self, pipeline_bundles_yaml_file):
        op = ModTaskSetBundleOperation("nonexistent", self.NEW_BUNDLE)

        loaded_doc = load_yaml(pipeline_bundles_yaml_file)
        style = YAMLStyle.detect(pipeline_bundles_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        with pytest.raises(TaskNotFoundError):
            op._do_action(tasks, ["spec", "tasks"], pipeline_bundles_yaml_file, style)

    def test_handle_pipeline_file(self, pipeline_bundles_yaml_file):
        op = ModTaskSetBundleOperation("clair-scan", self.NEW_BUNDLE)

        loaded_doc = load_yaml(pipeline_bundles_yaml_file)
        style = YAMLStyle.detect(pipeline_bundles_yaml_file)

        op.handle_pipeline_file(pipeline_bundles_yaml_file, loaded_doc, style)

        doc = load_yaml(pipeline_bundles_yaml_file)
        task = next(t for t in doc["spec"]["tasks"] if t["name"] == "clair-scan")
        bundle_param = next(p for p in task["taskRef"]["params"] if p["name"] == "bundle")
        assert bundle_param["value"] == self.NEW_BUNDLE

    def test_handle_pipeline_run_file(self, pipeline_run_bundles_yaml_file):
        op = ModTaskSetBundleOperation("clair-scan", self.NEW_BUNDLE)

        loaded_doc = load_yaml(pipeline_run_bundles_yaml_file)
        style = YAMLStyle.detect(pipeline_run_bundles_yaml_file)

        op.handle_pipeline_run_file(pipeline_run_bundles_yaml_file, loaded_doc, style)

        doc = load_yaml(pipeline_run_bundles_yaml_file)
        task = next(t for t in doc["spec"]["pipelineSpec"]["tasks"] if t["name"] == "clair-scan")
        bundle_param = next(p for p in task["taskRef"]["params"] if p["name"] == "bundle")
        assert bundle_param["value"] == self.NEW_BUNDLE

    def test_handle_pipeline_file_finally(self, create_yaml_file):
        content = dedent("""\
            apiVersion: tekton.dev/v1
            kind: Pipeline
            metadata:
              name: test-pipeline
            spec:
              finally:
                - name: clair-scan
                  taskRef:
                    resolver: bundles
                    params:
                      - name: name
                        value: task-clair-scan
                      - name: bundle
                        value: quay.io/org/task-clair-scan:0.1@sha256:abc123
                      - name: kind
                        value: task
            """)
        pipeline_file = create_yaml_file(content)
        op = ModTaskSetBundleOperation("clair-scan", self.NEW_BUNDLE)

        loaded_doc = load_yaml(pipeline_file)
        style = YAMLStyle.detect(pipeline_file)

        op.handle_pipeline_file(pipeline_file, loaded_doc, style)

        doc = load_yaml(pipeline_file)
        task = next(t for t in doc["spec"]["finally"] if t["name"] == "clair-scan")
        bundle_param = next(p for p in task["taskRef"]["params"] if p["name"] == "bundle")
        assert bundle_param["value"] == self.NEW_BUNDLE


class TestComplexScenarios:
    """Test complex scenarios involving multiple operations."""

    def test_multiple_add_operations(self, pipeline_yaml_file):
        """Test performing multiple add operations on the same file."""
        # Add first parameter
        op1 = ModTaskAddParamOperation("clone", "timeout", "30m")
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]
        result1 = op1._do_action(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result1 is True

        # Add second parameter
        op2 = ModTaskAddParamOperation("clone", "depth", "1")
        loaded_doc = load_yaml(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]
        result2 = op2._do_action(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result2 is True

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
                    - name: url
                      value: "https://github.com/example/repo"
                    - name: revision
                      value: "main"
                    - name: timeout
                      value: 30m
                    - name: depth
                      value: '1'
                - name: build
                  taskRef:
                    name: buildah
                  params:
                    - name: IMAGE
                      value: "registry.io/app:latest"
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_yaml_file) == expected

    def test_add_then_remove_param(self, pipeline_yaml_file):
        """Test adding a parameter and then removing it."""
        # Add parameter
        op_add = ModTaskAddParamOperation("clone", "timeout", "30m")
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]
        result_add = op_add._do_action(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result_add is True

        # Remove parameter
        op_remove = ModTaskRemoveParamOperation("clone", "timeout")
        loaded_doc = load_yaml(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]
        result_remove = op_remove._do_action(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result_remove is True

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
                    - name: url
                      value: "https://github.com/example/repo"
                    - name: revision
                      value: "main"
                - name: build
                  taskRef:
                    name: buildah
                  params:
                    - name: IMAGE
                      value: "registry.io/app:latest"
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_yaml_file) == expected

    def test_operations_on_different_tasks(self, pipeline_yaml_file):
        """Test performing operations on different tasks in the same pipeline."""
        # Add param to clone task
        op1 = ModTaskAddParamOperation("clone", "timeout", "30m")
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]
        result1 = op1._do_action(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result1 is True

        # Add param to build task
        op2 = ModTaskAddParamOperation("build", "CONTEXT", "./")
        loaded_doc = load_yaml(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]
        result2 = op2._do_action(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result2 is True

        # Remove param from build task
        op3 = ModTaskRemoveParamOperation("build", "IMAGE")
        loaded_doc = load_yaml(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]
        result3 = op3._do_action(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result3 is True

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
                    - name: url
                      value: "https://github.com/example/repo"
                    - name: revision
                      value: "main"
                    - name: timeout
                      value: 30m
                - name: build
                  taskRef:
                    name: buildah
                  params:
                    - name: CONTEXT
                      value: ./
                - name: test-task
                  taskRef:
                    name: test-runner
            """)

        assert read_file_content(pipeline_yaml_file) == expected
