import difflib
import os
import shutil
import tempfile
from pathlib import Path


def dry_run(file_path, mutate) -> None:
    """Run mutate on a temp copy and print a unified diff; leave the original untouched."""
    path = Path(file_path)
    try:
        file_desc, tmp_name = tempfile.mkstemp(suffix=path.suffix)
    except OSError as e:
        raise RuntimeError(f"Failed to create temp file for dry-run of {path}: {e}") from e
    os.close(file_desc)
    tmp = Path(tmp_name)
    try:
        shutil.copy(path, tmp)
        mutate(str(tmp))
        print(
            "".join(
                difflib.unified_diff(
                    path.read_text(encoding="utf-8").splitlines(True),
                    tmp.read_text(encoding="utf-8").splitlines(True),
                    fromfile=str(path),
                    tofile=str(path),
                )
            ),
            end="",
        )
    finally:
        tmp.unlink(missing_ok=True)
