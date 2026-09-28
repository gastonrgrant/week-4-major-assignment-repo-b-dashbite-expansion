import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def stage_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.module:
            if node.module.startswith("pipeline."):
                found.add(node.module.split(".", 1)[1])
            if node.module == "pipeline":
                found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("pipeline."):
                    found.add(alias.name.split(".", 1)[1])
    return found


def test_infer_does_not_import_train():
    assert "train" not in stage_imports(ROOT / "pipeline" / "infer.py")


def test_dashboard_does_not_import_stages():
    imported = stage_imports(ROOT / "pipeline" / "dashboard.py")
    assert imported.isdisjoint({"simulator", "preprocess", "train", "infer"})


def test_pulse_does_not_import_stages():
    imported = stage_imports(ROOT / "pipeline" / "pulse.py")
    assert imported.isdisjoint({"simulator", "preprocess", "train", "infer", "dashboard"})
