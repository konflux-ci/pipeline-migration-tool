## Project overview

Pipeline Migration Tool (`pmt`) is a CLI tool for applying migrations to Konflux CI build pipelines.
It discovers migrations attached to Tekton task bundles as OCI artifacts and applies them to `Pipeline` or `PipelineRun` YAML files.
It is primarily invoked by Mintmaker/Renovate as a post-upgrade command.

## Setup

Requires Python 3.12+. Create the development environment:

```bash
make venv/create
source .venv/bin/activate
```

To update dependencies after changes to `pyproject.toml`:

```bash
source .venv/bin/activate
make deps/compile
```

## Running tests

Run a specific test file:

```bash
source .venv/bin/activate
tox -e py312 -- tests/test_yamleditor.py
```

## Code style

- Formatter: **Black** with `--line-length 100`
- Linter: **Flake8** with `max-line-length = 100`
- Type checker: **mypy** (strict missing imports ignored)
- Run all checks: `tox -e black,flake8,mypy`

Per-file usage:

```bash
python3 -m black --line-length 100 path/to/file.py
python3 -m flake8 path/to/file.py
python3 -m mypy path/to/file.py
```

## Key conventions

- **YAML editing**: The `yamleditor` module edits YAML as raw text to produce minimal diffs. Do not use `ruamel.yaml` dumping to write pipeline files — always go through `yamleditor` for modifications to user pipeline files.
- **Test structure**: Tests mirror `src/` layout under `tests/`. CLI tests (`*_cli.py`) test argument parsing and end-to-end command behavior. Other test files test the underlying logic directly.
- **HTTP mocking**: Tests use the `responses` library to mock HTTP calls to OCI registries and Quay API.
- **No interactive input**: The tool runs unattended in Renovate post-upgrade hooks. Never add interactive prompts.

## Domain context

- **Task bundles** are OCI images containing Tekton task definitions, referenced by digest in pipeline YAML files.
- **Migrations** are shell scripts attached to task bundles as OCI artifacts. They are discovered via annotations (`dev.konflux-ci.task.has-migration`, `dev.konflux-ci.task.is-migration`).
- Pipeline files live in `.tekton/` directories by convention and are either `Pipeline` or `PipelineRun` Kubernetes resources.

## Release process

Versions follow `0.minor.patch`. Bump the version in `src/pipeline_migration/__init__.py`. See the README for full release steps.
