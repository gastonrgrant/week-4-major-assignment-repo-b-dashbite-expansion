from pathlib import Path


def pytest_collection_modifyitems(config, items):
    for item in items:
        path = Path(str(item.fspath))
        if "unit" in path.parts:
            item.add_marker("unit")
        elif "regression" in path.parts:
            item.add_marker("regression")
        elif "integration" in path.parts:
            item.add_marker("integration")
