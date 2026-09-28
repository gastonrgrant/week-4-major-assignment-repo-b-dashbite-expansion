from __future__ import annotations

import os
from pathlib import Path

DIR_NAMES = ("raw", "features", "models", "predictions", "quality")


def data_dirs(root: Path | None = None) -> dict[str, Path]:
    if root is None:
        base = Path(os.environ.get("DASHBITE_DATA_ROOT", "data"))
    else:
        base = Path(root)
    return {name: base / name for name in DIR_NAMES}


def ensure_data_dirs(root: Path | None = None) -> dict[str, Path]:
    dirs = data_dirs(root)
    for path in dirs.values():
        path.mkdir(parents=True, exist_ok=True)
    return dirs
