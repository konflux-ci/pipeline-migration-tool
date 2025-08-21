import tempfile
import pytest
from pathlib import Path
from textwrap import dedent

from pipeline_migration.actions.modify.task import (
    ModTaskAddParamOperation,
    ModTaskRemoveParamOperation,
)
from pipeline_migration.utils import load_yaml, YAMLStyle


@pytest.fixture
def pipeline_yaml_file():
    """Create a temporary YAML file with a pipeline structure."""
    content = dedent(
        """\
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
        """
    )

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml", encoding="utf-8") as f:
        f.write(content)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    try:
        temp_path.unlink()
    except OSError:
        pass


@pytest.fixture
def pipeline_run_yaml_file():
    """Create a temporary YAML file with a PipelineRun structure."""
    content = dedent(
        """\
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
        """
    )

    with tempfile.NamedTemporaryFile(mode="w", delete=False, suffix=".yaml", encoding="utf-8") as f:
        f.write(content)
        temp_path = Path(f.name)

    yield temp_path

    # Cleanup
    try:
        temp_path.unlink()
    except OSError:
        pass


class TestModTaskAddParamOperation:
    """Test cases for ModTaskAddParamOperation class."""

    def test_initialization(self):
        """Test operation initialization."""
        op = ModTaskAddParamOperation("clone", "timeout", "30m", git_add=True)
        assert op.task_name == "clone"
        assert op.param_name == "timeout"
        assert op.param_value == "30m"
        assert op.git_add is True

    def test_add_param_to_existing_params_list(self, pipeline_yaml_file):
        """Test adding a parameter to a task that already has parameters."""
        op = ModTaskAddParamOperation("clone", "timeout", "30m")

        # Load initial data
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._add_param(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result is True

        # Verify the parameter was added
        updated_doc = load_yaml(pipeline_yaml_file)
        clone_task = next(task for task in updated_doc["spec"]["tasks"] if task["name"] == "clone")
        param_names = [param["name"] for param in clone_task["params"]]
        assert "timeout" in param_names

        timeout_param = next(param for param in clone_task["params"] if param["name"] == "timeout")
        assert timeout_param["value"] == "30m"

    def test_add_param_to_task_without_params(self, pipeline_yaml_file):
        """Test adding a parameter to a task that has no existing parameters."""
        op = ModTaskAddParamOperation("test-task", "verbose", "true")

        # Load initial data
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._add_param(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result is True

        # Verify the parameter was added
        updated_doc = load_yaml(pipeline_yaml_file)
        test_task = next(
            task for task in updated_doc["spec"]["tasks"] if task["name"] == "test-task"
        )
        assert "params" in test_task
        assert len(test_task["params"]) == 1
        assert test_task["params"][0]["name"] == "verbose"
        assert test_task["params"][0]["value"] == "true"

    def test_update_existing_param_value(self, pipeline_yaml_file):
        """Test updating an existing parameter value."""
        op = ModTaskAddParamOperation("clone", "url", "https://github.com/new/repo")

        # Load initial data
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._add_param(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result is True

        # Verify the parameter was updated
        updated_doc = load_yaml(pipeline_yaml_file)
        clone_task = next(task for task in updated_doc["spec"]["tasks"] if task["name"] == "clone")
        url_param = next(param for param in clone_task["params"] if param["name"] == "url")
        assert url_param["value"] == "https://github.com/new/repo"

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
        result = op._add_param(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result is True

        # Verify the parameter was updated
        updated_doc = load_yaml(pipeline_yaml_file)
        clone_task = next(task for task in updated_doc["spec"]["tasks"] if task["name"] == "clone")
        url_param = next(param for param in clone_task["params"] if param["name"] == "url")
        assert url_param["value"] == ["https://github.com/new/repo", "another_url"]

    def test_no_change_when_param_value_same(self, pipeline_yaml_file):
        """Test that no change is made when parameter value is already the same."""
        op = ModTaskAddParamOperation("clone", "url", "https://github.com/example/repo")

        # Load initial data
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._add_param(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result is False  # No change needed

    def test_task_not_found(self, pipeline_yaml_file):
        """Test behavior when specified task doesn't exist."""
        op = ModTaskAddParamOperation("nonexistent-task", "param", "value")

        # Load initial data
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._add_param(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result is False

    def test_handle_pipeline_file(self, pipeline_yaml_file):
        """Test handle_pipeline_file method."""
        op = ModTaskAddParamOperation("clone", "timeout", "30m")

        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)

        # This should not raise an exception
        op.handle_pipeline_file(pipeline_yaml_file, loaded_doc, style)

        # Verify the parameter was added
        updated_doc = load_yaml(pipeline_yaml_file)
        clone_task = next(task for task in updated_doc["spec"]["tasks"] if task["name"] == "clone")
        param_names = [param["name"] for param in clone_task["params"]]
        assert "timeout" in param_names

    def test_handle_pipeline_run_file(self, pipeline_run_yaml_file):
        """Test handle_pipeline_run_file method."""
        op = ModTaskAddParamOperation("clone", "timeout", "30m")

        loaded_doc = load_yaml(pipeline_run_yaml_file)
        style = YAMLStyle.detect(pipeline_run_yaml_file)

        # This should not raise an exception
        op.handle_pipeline_run_file(pipeline_run_yaml_file, loaded_doc, style)

        # Verify the parameter was added
        updated_doc = load_yaml(pipeline_run_yaml_file)
        clone_task = next(
            task for task in updated_doc["spec"]["pipelineSpec"]["tasks"] if task["name"] == "clone"
        )
        param_names = [param["name"] for param in clone_task["params"]]
        assert "timeout" in param_names


class TestModTaskRemoveParamOperation:
    """Test cases for ModTaskRemoveParamOperation class."""

    def test_initialization(self):
        """Test operation initialization."""
        op = ModTaskRemoveParamOperation("clone", "timeout", git_add=True)
        assert op.task_name == "clone"
        assert op.param_name == "timeout"
        assert op.git_add is True

    def test_remove_existing_param(self, pipeline_yaml_file):
        """Test removing an existing parameter."""
        op = ModTaskRemoveParamOperation("clone", "url")

        # Load initial data
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._remove_param(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result is True

        # Verify the parameter was removed
        updated_doc = load_yaml(pipeline_yaml_file)
        clone_task = next(task for task in updated_doc["spec"]["tasks"] if task["name"] == "clone")
        param_names = [param["name"] for param in clone_task["params"]]
        assert "url" not in param_names
        assert "revision" in param_names  # Other params should remain

    def test_remove_param_from_task_without_params(self, pipeline_yaml_file):
        """Test removing a parameter from a task that has no parameters."""
        op = ModTaskRemoveParamOperation("test-task", "nonexistent")

        # Load initial data
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._remove_param(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result is False

    def test_remove_nonexistent_param(self, pipeline_yaml_file):
        """Test removing a parameter that doesn't exist."""
        op = ModTaskRemoveParamOperation("clone", "nonexistent-param")

        # Load initial data
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._remove_param(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result is False

    def test_task_not_found(self, pipeline_yaml_file):
        """Test behavior when specified task doesn't exist."""
        op = ModTaskRemoveParamOperation("nonexistent-task", "param")

        # Load initial data
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]

        # Execute operation
        result = op._remove_param(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result is False

    def test_handle_pipeline_file(self, pipeline_yaml_file):
        """Test handle_pipeline_file method."""
        op = ModTaskRemoveParamOperation("clone", "url")

        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)

        # This should not raise an exception
        op.handle_pipeline_file(pipeline_yaml_file, loaded_doc, style)

        # Verify the parameter was removed
        updated_doc = load_yaml(pipeline_yaml_file)
        clone_task = next(task for task in updated_doc["spec"]["tasks"] if task["name"] == "clone")
        param_names = [param["name"] for param in clone_task["params"]]
        assert "url" not in param_names

    def test_handle_pipeline_run_file(self, pipeline_run_yaml_file):
        """Test handle_pipeline_run_file method."""
        op = ModTaskRemoveParamOperation("deploy", "namespace")

        loaded_doc = load_yaml(pipeline_run_yaml_file)
        style = YAMLStyle.detect(pipeline_run_yaml_file)

        # This should not raise an exception
        op.handle_pipeline_run_file(pipeline_run_yaml_file, loaded_doc, style)

        # Verify the parameter was removed
        updated_doc = load_yaml(pipeline_run_yaml_file)
        deploy_task = next(
            task
            for task in updated_doc["spec"]["pipelineSpec"]["tasks"]
            if task["name"] == "deploy"
        )
        param_names = [param["name"] for param in deploy_task["params"]]
        assert "namespace" not in param_names
        assert "image" in param_names  # Other params should remain

    def test_remove_last_param_leaves_empty_params_section(self, pipeline_yaml_file):
        """Test that removing the last parameter leaves an empty params section."""
        # First add a task with only one parameter
        op_add = ModTaskAddParamOperation("test-task", "single-param", "value")
        loaded_doc = load_yaml(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]
        style = YAMLStyle.detect(pipeline_yaml_file)

        op_add._add_param(tasks, ["spec", "tasks"], pipeline_yaml_file, style)

        # Now remove that parameter
        op_remove = ModTaskRemoveParamOperation("test-task", "single-param")
        loaded_doc = load_yaml(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]
        result = op_remove._remove_param(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result is True

        # parent parameter should be removed when empty
        updated_doc = load_yaml(pipeline_yaml_file)
        test_task = next(
            task for task in updated_doc["spec"]["tasks"] if task["name"] == "test-task"
        )
        assert test_task.get("params") is None


class TestComplexScenarios:
    """Test complex scenarios involving multiple operations."""

    def test_multiple_add_operations(self, pipeline_yaml_file):
        """Test performing multiple add operations on the same file."""
        # Add first parameter
        op1 = ModTaskAddParamOperation("clone", "timeout", "30m")
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]
        result1 = op1._add_param(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result1 is True

        # Add second parameter
        op2 = ModTaskAddParamOperation("clone", "depth", "1")
        loaded_doc = load_yaml(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]
        result2 = op2._add_param(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result2 is True

        # Verify both parameters were added
        updated_doc = load_yaml(pipeline_yaml_file)
        clone_task = next(task for task in updated_doc["spec"]["tasks"] if task["name"] == "clone")
        param_names = [param["name"] for param in clone_task["params"]]
        assert "timeout" in param_names
        assert "depth" in param_names
        assert "url" in param_names  # Original param should still be there
        assert "revision" in param_names  # Original param should still be there

    def test_add_then_remove_param(self, pipeline_yaml_file):
        """Test adding a parameter and then removing it."""
        # Add parameter
        op_add = ModTaskAddParamOperation("clone", "timeout", "30m")
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]
        result_add = op_add._add_param(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result_add is True

        # Remove parameter
        op_remove = ModTaskRemoveParamOperation("clone", "timeout")
        loaded_doc = load_yaml(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]
        result_remove = op_remove._remove_param(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result_remove is True

        # Verify parameter is gone
        updated_doc = load_yaml(pipeline_yaml_file)
        clone_task = next(task for task in updated_doc["spec"]["tasks"] if task["name"] == "clone")
        param_names = [param["name"] for param in clone_task["params"]]
        assert "timeout" not in param_names
        assert "url" in param_names  # Original params should still be there
        assert "revision" in param_names

    def test_operations_on_different_tasks(self, pipeline_yaml_file):
        """Test performing operations on different tasks in the same pipeline."""
        # Add param to clone task
        op1 = ModTaskAddParamOperation("clone", "timeout", "30m")
        loaded_doc = load_yaml(pipeline_yaml_file)
        style = YAMLStyle.detect(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]
        result1 = op1._add_param(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result1 is True

        # Add param to build task
        op2 = ModTaskAddParamOperation("build", "CONTEXT", "./")
        loaded_doc = load_yaml(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]
        result2 = op2._add_param(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result2 is True

        # Remove param from build task
        op3 = ModTaskRemoveParamOperation("build", "IMAGE")
        loaded_doc = load_yaml(pipeline_yaml_file)
        tasks = loaded_doc["spec"]["tasks"]
        result3 = op3._remove_param(tasks, ["spec", "tasks"], pipeline_yaml_file, style)
        assert result3 is True

        # Verify all changes
        updated_doc = load_yaml(pipeline_yaml_file)

        clone_task = next(task for task in updated_doc["spec"]["tasks"] if task["name"] == "clone")
        clone_param_names = [param["name"] for param in clone_task["params"]]
        assert "timeout" in clone_param_names

        build_task = next(task for task in updated_doc["spec"]["tasks"] if task["name"] == "build")
        build_param_names = [param["name"] for param in build_task["params"]]
        assert "CONTEXT" in build_param_names
        assert "IMAGE" not in build_param_names
