from importlib.metadata import version

# The version is defined in the VERSION file at the repository root and baked into the
# package metadata by setuptools at build time (see [tool.setuptools.dynamic] in pyproject.toml).
__version__ = version("pipeline-migration-tool")
