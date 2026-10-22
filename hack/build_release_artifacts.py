#!/usr/bin/env python3
"""Build a sdist and a wheel for the current revision via `python3 -m build`,
plus a zip of each (the release-to-github pipeline's upload step only globs
*.zip and *.json out of the image -- .tar.gz and .whl files are extracted
into the image but never attached to the release), a SHA256SUMS file, and a
JSON manifest. GitHub already attaches a raw source snapshot to releases
automatically, so this does not duplicate that -- it only builds the
installable artifacts. Runs with --no-isolation, so `build` and its backend
(setuptools, pinned in requirements-build.txt) must already be installed --
no network access is required or used.
"""

import hashlib
import json
import re
import shutil
import subprocess
import sys
import tarfile
import zipfile
from pathlib import Path

NAME = "pipeline-migration-tool"


def read_version(source_root: Path) -> str:
    """Extract __version__ from src/pipeline_migration/__init__.py."""
    init_py = source_root / "src" / "pipeline_migration" / "__init__.py"
    match = re.search(r'__version__ = "([^"]+)"', init_py.read_text())
    if not match:
        raise SystemExit(f"could not find __version__ in {init_py}")
    return match.group(1)


def sha256sum(path: Path) -> str:
    """Return the hex-encoded SHA256 digest of path's contents."""
    digest = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_artifacts(source_root: Path, out_dir: Path) -> list:
    """Run `python3 -m build --no-isolation` and return the newly created artifact paths."""
    before = set(out_dir.iterdir())
    cmd = [
        sys.executable,
        "-m",
        "build",
        "--no-isolation",
        "--outdir",
        str(out_dir),
        str(source_root),
    ]
    subprocess.run(cmd, check=True)
    return sorted(set(out_dir.iterdir()) - before)


def tarball_to_zip(tar_path: Path) -> Path:
    """Repack a gzip tarball's contents into a sibling zip file."""
    zip_path = tar_path.with_suffix("").with_suffix(".zip")
    with tarfile.open(tar_path, "r:gz") as tar:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for member in tar.getmembers():
                if not member.isfile():
                    continue
                extracted = tar.extractfile(member)
                if extracted is None:
                    raise RuntimeError(f"could not extract {member.name}")
                zf.writestr(member.name, extracted.read())
    return zip_path


def main() -> None:
    """Build the sdist, wheel, and their zip mirrors, a JSON manifest, and SHA256SUMS."""
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} <output-dir>")

    source_root = Path(".").resolve()
    out_dir = Path(sys.argv[1])
    out_dir.mkdir(parents=True, exist_ok=True)

    version = read_version(source_root)
    artifacts = build_artifacts(source_root, out_dir)

    sdist_tarball = next(p for p in artifacts if p.name.endswith(".tar.gz"))
    artifacts.append(tarball_to_zip(sdist_tarball))

    wheel = next(p for p in artifacts if p.suffix == ".whl")
    wheel_zip = wheel.with_suffix(".whl.zip")
    shutil.copy2(wheel, wheel_zip)
    artifacts.append(wheel_zip)

    manifest_path = out_dir / f"{NAME}-{version}.json"
    sums_path = out_dir / f"{NAME}_{version}_SHA256SUMS"

    manifest = {
        "name": NAME,
        "version": version,
        "artifacts": [artifact.name for artifact in artifacts],
    }
    manifest_path.write_text(json.dumps(manifest, indent=2) + "\n")

    with sums_path.open("w") as f:
        for artifact in (*artifacts, manifest_path):
            f.write(f"{sha256sum(artifact)}  {artifact.name}\n")


if __name__ == "__main__":
    main()
