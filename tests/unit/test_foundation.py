from pipeline.config import load_config
from pipeline.paths import data_dirs, ensure_data_dirs


def test_load_config_defaults(monkeypatch):
    for name in ("TRAIN_EVERY_N_EVENTS", "BATCH_SIZE", "POLL_INTERVAL_SECONDS"):
        monkeypatch.delenv(name, raising=False)
    config = load_config()
    assert config.train_every_n_events == 2000
    assert config.batch_size == 50
    assert config.poll_interval_seconds == 15


def test_load_config_env_override(monkeypatch):
    monkeypatch.setenv("TRAIN_EVERY_N_EVENTS", "3")
    monkeypatch.setenv("BATCH_SIZE", "7")
    monkeypatch.setenv("POLL_INTERVAL_SECONDS", "2")
    config = load_config()
    assert str(config) == "TRAIN_EVERY_N_EVENTS=3 BATCH_SIZE=7 POLL_INTERVAL_SECONDS=2"


def test_paths_resolve_under_root(tmp_path):
    dirs = data_dirs(tmp_path)
    assert set(dirs) == {"raw", "features", "models", "predictions", "quality"}
    assert dirs["features"] == tmp_path / "features"
    assert not dirs["raw"].exists()


def test_ensure_data_dirs_creates_five(tmp_path):
    dirs = ensure_data_dirs(tmp_path)
    for path in dirs.values():
        assert path.is_dir()
