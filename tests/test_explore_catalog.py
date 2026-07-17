import importlib.util
from pathlib import Path


def _load_explore_catalog_module():
    script = Path(__file__).parents[1] / "scripts" / "explore_catalog.py"
    spec = importlib.util.spec_from_file_location("explore_catalog", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_emit_format_normalizes_none_namespace_to_an_empty_column(capsys):
    explore_catalog = _load_explore_catalog_module()
    model = {
        "slug": "example/model",
        "pulls": 1,
        "tags_count": 1,
        "model_type": "community",
        "namespace": None,
        "updated": "today",
        "capabilities": [],
        "blurb": "example",
        "variants": [],
    }

    explore_catalog.emit_format([model], "tsv")

    row = capsys.readouterr().out.splitlines()[1].split("\t")
    assert row[4] == ""
