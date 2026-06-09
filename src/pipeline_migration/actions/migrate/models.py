from functools import cached_property
from dataclasses import dataclass, field

from pipeline_migration.actions.migrate.constants import REGEX_PMT_MODIFY_USAGE


@dataclass
class TaskBundleMigration:
    """Represents a migration script attached to a task bundle."""

    # A complete image reference with both tag and digest
    task_bundle: str
    # Content of the script
    migration_script: str

    @cached_property
    def is_pmt_modify_used(self) -> bool:
        """Check whether the migration script uses the pmt modify command."""
        return REGEX_PMT_MODIFY_USAGE.search(self.migration_script) is not None


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
    parent_dir: str  # Renovate template field parentDir

    task_bundle_upgrades: list[TaskBundleUpgrade] = field(default_factory=list)
