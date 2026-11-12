from functools import cached_property
from dataclasses import dataclass, field

from pipeline_migration.actions.migrate.constants import (
    REGEX_PMT_API_VERSION,
    REGEX_PMT_MODIFY_USAGE,
)
from pipeline_migration.api_version import MIGRATION_API_VERSION, ApiVersion


@dataclass
class TaskBundleMigration:
    """Represents a migration script attached to a task bundle."""

    # A complete image reference with both tag and digest
    task_bundle: str
    # Content of the script
    migration_script: str

    @cached_property
    def is_pmt_modify_used(self) -> bool:
        """Check whether the migration script uses pmt commands modifying pipelines."""
        return REGEX_PMT_MODIFY_USAGE.search(self.migration_script) is not None

    @cached_property
    def declared_api_version(self) -> int | None:
        """API version the script sets via PMT_API_VERSION, or None if it sets none.

        Found by static analysis. Scripts are expected to declare the version once, at the top.
        """
        match = REGEX_PMT_API_VERSION.search(self.migration_script)
        return int(match.group(1)) if match else None

    @property
    def api_version_description(self) -> str:
        """Describe the API version the script runs with, for logging."""
        version = self.declared_api_version
        if version is None:
            return f"{MIGRATION_API_VERSION}, default"
        if version not in {v.value for v in ApiVersion}:
            return f"{version}, unsupported"
        return str(version)


@dataclass
class TaskBundleUpgrade:
    """Represents a task bundle upgrade from one version to another."""

    dep_name: str  # Renovate template field: depName
    current_value: str  # Renovate template field: currentValue. It is the image tag.
    current_digest: str  # Renovate template field: currentDigest
    new_value: str  # Renovate template field: newValue. It is the image tag.
    new_digest: str  # Renovate template field: newDigest

    migrations: list[TaskBundleMigration] = field(default_factory=list)

    @property
    def current_bundle(self) -> str:
        """Return the full image reference for the current bundle."""
        return f"{self.dep_name}:{self.current_value}@{self.current_digest}"

    @property
    def new_bundle(self) -> str:
        """Return the full image reference for the new bundle."""
        return f"{self.dep_name}:{self.new_value}@{self.new_digest}"


@dataclass
class PackageFile:
    """Groups task bundle upgrades for a single pipeline file."""

    file_path: str  # Renovate template field packageFile

    task_bundle_upgrades: list[TaskBundleUpgrade] = field(default_factory=list)
