from pathlib import Path

from pipeline.paths import data_dirs

ROOT = Path(__file__).resolve().parents[2]


def entrypoint_text() -> str:
    for path in (ROOT / "docker-entrypoint.sh", Path("/usr/local/bin/docker-entrypoint.sh")):
        if path.is_file():
            return path.read_text(encoding="utf-8")
    raise AssertionError("docker-entrypoint.sh missing")


def test_default_data_root_stays_data(monkeypatch):
    monkeypatch.delenv("DASHBITE_DATA_ROOT", raising=False)
    assert data_dirs()["raw"] == Path("data") / "raw"


def test_compose_points_workers_at_data_volume():
    text = (ROOT / "docker-compose.yml").read_text(encoding="utf-8")
    assert "DASHBITE_DATA_ROOT: /data" in text
    assert "dashbite-data:/data" in text
    for service in ("simulator", "preprocess", "train", "infer", "dashboard"):
        assert f"pipeline.{service}" in text or "pipeline/dashboard.py" in text
    assert "pipeline.simulator" in text
    assert "pipeline.preprocess" in text
    assert "pipeline.train" in text
    assert "pipeline.infer" in text
    assert "pipeline/dashboard.py" in text


def test_entrypoint_execs_worker_as_dashbite():
    text = entrypoint_text()
    assert "export HOME=/home/dashbite" in text
    assert "exec setpriv --reuid=dashbite --regid=dashbite --init-groups --" in text
    assert "exec runuser" not in text
