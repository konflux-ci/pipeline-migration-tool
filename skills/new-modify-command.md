---
name: New modify subcommand
description: Use this skill when asked to create a new `pmt modify <subcommand>` — a new subcommand under the existing `modify` command in pipeline-migration-tool.
---

## Before you start

1. **Clarify requirements** — ask the user:
   - What is the subcommand name? (e.g. `workspace`, `annotation`, `label`)
   - What operations does it need? (e.g. `add`, `remove`, `replace`)
   - What Tekton resource fields does it target?
   - Should it work on Pipeline, PipelineRun, or both?

2. **Read the existing patterns** — read these files to understand conventions before writing any code:
   - `src/pipeline_migration/actions/modify/__init__.py` — how subcommands are registered
   - `src/pipeline_migration/actions/modify/task.py` — the canonical example: CLI registration, Operation classes, action functions
   - `src/pipeline_migration/pipeline.py` — `PipelineFileOperation` base class and `iterate_files_or_dirs`
   - `src/pipeline_migration/yamleditor.py` — `EditYAMLEntry` and `YAMLPath` for surgical YAML edits
   - `src/pipeline_migration/cli.py` — top-level CLI wiring (you won't change this file)

3. **Read existing tests** for the pattern:
   - `tests/actions/modify/test_task_cli.py` — CLI integration tests
   - `tests/actions/modify/test_task.py` — unit tests for Operation classes

## Architecture overview

```
pmt modify -f <file-or-dir> <subcommand> [args...]
```

The `modify` command is a two-level subcommand hierarchy:
- `modify` itself registers the shared `-f`/`--file-or-dir` argument
- Each subcommand (`task`, `generic`, and your new one) registers its own arguments and operations

Each subcommand follows this structure:

```
register_cli(subparser)          # argparse registration
  └── subparser with operations  # e.g. add-param, remove-param
       └── set_defaults(action=action_fn)

OperationClass(PipelineFileOperation)
  ├── handle_pipeline_file()     # handles kind: Pipeline
  └── handle_pipeline_run_file() # handles kind: PipelineRun

action_fn(args)                  # wires CLI args → Operation → file iteration
```

## Step-by-step implementation

### Step 1: Create the subcommand module

Create `src/pipeline_migration/actions/modify/<subcommand>.py` with this structure:

```python
import argparse
import logging
from pathlib import Path
from typing import Any, Final, List

from pipeline_migration.yamleditor import EditYAMLEntry, YAMLPath
from pipeline_migration.types import FilePath
from pipeline_migration.utils import YAMLStyle
from pipeline_migration.pipeline import PipelineFileOperation, iterate_files_or_dirs

logger = logging.getLogger("modify.<subcommand>")


SUBCMD_DESCRIPTION: Final = """\
<Detailed description with usage examples, following the format in task.py>
"""


def register_cli(subparser) -> None:
    """Register the subcommand and its operations with argparse."""
    parser = subparser.add_parser(
        "<subcommand-name>",
        help="<One-line help>",
        description=SUBCMD_DESCRIPTION,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    # Add subcommand-level positional args (e.g. task_name in task.py)
    parser.add_argument(
        "<positional>",
        metavar="<METAVAR>",
        help="<help text>",
    )

    # Create sub-parser for operations (add, remove, etc.)
    subparser_ops = parser.add_subparsers(
        title="subcommands to modify <resource>", required=True
    )

    # Register each operation
    op_parser = subparser_ops.add_parser(
        "<operation-name>",
        help="<operation help>",
    )
    op_parser.add_argument(...)
    op_parser.set_defaults(action=action_<operation>)


class <Name>Operation(PipelineFileOperation):
    """Operation that modifies <resource> in pipeline YAML files."""

    def __init__(self, <params>) -> None:
        super().__init__()
        # Store operation parameters

    def handle_pipeline_file(
        self, file_path: FilePath, loaded_doc: Any, style: YAMLStyle
    ) -> None:
        # YAML paths for Pipeline kind
        # e.g. ["spec", "tasks"] or ["spec", "finally"]
        ...

    def handle_pipeline_run_file(
        self, file_path: FilePath, loaded_doc: Any, style: YAMLStyle
    ) -> None:
        # YAML paths for PipelineRun kind
        # e.g. ["spec", "pipelineSpec", "tasks"]
        ...


def action_<operation>(args) -> None:
    """Action function wired to argparse via set_defaults."""
    search_places = [path for path in args.file_or_dir if path]
    relative_tekton_dir = Path("./.tekton")
    if not search_places and relative_tekton_dir.exists():
        search_places = [str(relative_tekton_dir.absolute())]

    op = <Name>Operation(<args fields>)
    for file_path in iterate_files_or_dirs(search_places):
        op.handle(str(file_path))
```

### Step 2: Register the subcommand

Edit `src/pipeline_migration/actions/modify/__init__.py`:

1. Add the import at the top alongside existing ones:
   ```python
   from pipeline_migration.actions.modify.<subcommand> import register_cli as register_mod_<subcommand>_cli
   ```

2. Add the registration call inside `register_cli()`, after the existing `register_mod_generic_cli(subparser_modify)` line:
   ```python
   register_mod_<subcommand>_cli(subparser_modify)
   ```

Do NOT modify `src/pipeline_migration/cli.py` — it already registers `modify`, and your subcommand is nested under it.

### Step 3: Write tests

Create two test files:

#### `tests/actions/modify/test_<subcommand>_cli.py` — CLI integration tests

```python
from pathlib import Path
from textwrap import dedent

import pytest

from pipeline_migration.cli import entry_point
from pipeline_migration.utils import load_yaml


@pytest.fixture
def component_pipeline_dir(tmp_path):
    """Create temporary pipeline files for testing."""
    tekton_dir = tmp_path / ".tekton"
    tekton_dir.mkdir(parents=True)

    # Create Pipeline YAML
    pipeline_file = tekton_dir / "pipeline.yaml"
    pipeline_file.write_text(dedent("""\
        apiVersion: tekton.dev/v1
        kind: Pipeline
        metadata:
          name: test-pipeline
        spec:
          tasks:
            - name: clone
              taskRef:
                name: git-clone
    """))

    # Create PipelineRun YAML
    pipeline_run_file = tekton_dir / "pipeline-run.yaml"
    pipeline_run_file.write_text(dedent("""\
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
    """))

    return tmp_path


class TestCli<Operation>:
    def test_<operation>_pipeline(self, component_pipeline_dir, monkeypatch):
        monkeypatch.chdir(component_pipeline_dir)
        monkeypatch.setattr(
            "sys.argv",
            ["pmt", "modify", "<subcommand>", "<args...>"],
        )
        entry_point()

        # Load and verify the modified YAML
        result = load_yaml(
            str(component_pipeline_dir / ".tekton" / "pipeline.yaml")
        )
        # Assert expected changes
        ...
```

#### `tests/actions/modify/test_<subcommand>.py` — unit tests for Operation classes

```python
import pytest

from pipeline_migration.actions.modify.<subcommand> import <Name>Operation


class Test<Name>Operation:
    def test_<scenario>(self, tmp_path):
        # Create a minimal YAML file
        # Instantiate the Operation
        # Call op.handle(str(file_path))
        # Verify the YAML was modified correctly
        ...
```

### Step 4: Verify

Run the following checks:

```bash
# Run the new tests
python -m pytest tests/actions/modify/test_<subcommand>_cli.py tests/actions/modify/test_<subcommand>.py -v

# Run the full test suite to check for regressions
tox

# Verify CLI help renders correctly
pmt modify --help
pmt modify <subcommand> --help
```

## Key patterns to follow

### YAML editing — always use EditYAMLEntry
Never modify YAML in memory and dump it back. Use `EditYAMLEntry` for minimal diffs that preserve comments and formatting:
```python
yamledit = EditYAMLEntry(pipeline_file, style=style)
yamledit.insert(path, new_data)   # add to dict/list
yamledit.replace(path, new_data)  # replace value at path
yamledit.delete(path)             # remove item at path
```

### YAML paths
Paths are `list[int | str]` — yq-style traversal. Build them incrementally:
```python
path = ["spec", "tasks"]        # start with section
path.append(index)              # add task index
path.append("params")           # descend into params
path.append(param_index)        # target specific param
```

### Pipeline vs PipelineRun paths
- **Pipeline**: `spec.tasks[*]`, `spec.finally[*]`
- **PipelineRun**: `spec.pipelineSpec.tasks[*]`, `spec.pipelineSpec.finally[*]`

Always handle both unless the operation is specific to one kind.

### File iteration — the standard action pattern
Every action function uses the same file-finding boilerplate:
```python
search_places = [path for path in args.file_or_dir if path]
relative_tekton_dir = Path("./.tekton")
if not search_places and relative_tekton_dir.exists():
    search_places = [str(relative_tekton_dir.absolute())]

op = MyOperation(...)
for file_path in iterate_files_or_dirs(search_places):
    op.handle(str(file_path))
```

### Logging
Use `logger.info()` for changes being made, `logger.warning()` for skipped files or missing resources. Follow the message style in `task.py`:
```python
logger.info("task '%s' in '%s': param '%s' will be created", ...)
logger.warning("task '%s' does not exist in '%s'", ...)
```

### Error handling
- Raise domain-specific exceptions (e.g. `TaskNotFoundError`) for expected conditions
- The top-level `entry_point()` in `cli.py` catches all exceptions and logs them
- Use `NotAPipelineFile` (from `pipeline.py`) for YAML structure issues — the base class handles this

## Common mistakes to avoid

- **Do not modify `cli.py`** — your subcommand is under `modify`, not a top-level command
- **Do not use `ruamel.yaml` directly for writes** — always go through `EditYAMLEntry`
- **Do not forget the `style` parameter** — pass `YAMLStyle` to `EditYAMLEntry` for consistent formatting
- **Do not hardcode Pipeline-only paths** — always handle both Pipeline and PipelineRun kinds
- **Do not use `path_prefix` by reference without copying** — lists are mutable; if you need to branch, copy first
- **Do not skip the `finally` section** — tasks can be in both `spec.tasks` and `spec.finally`
