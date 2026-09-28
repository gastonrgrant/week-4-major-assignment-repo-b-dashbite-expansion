from __future__ import annotations

import sys
from pathlib import Path

from pipeline.paths import data_dirs
from pipeline.runtime import heartbeat_fresh, heartbeat_max_age, heartbeat_path


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit("usage: python -m pipeline.health <stage>")
    path = heartbeat_path(Path(data_dirs()["raw"]).parent, sys.argv[1])
    if not heartbeat_fresh(path, heartbeat_max_age()):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
