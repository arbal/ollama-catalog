import importlib.util
from pathlib import Path
from rich.console import Console


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


def test_filters_decision_and_modalities_and_uses_explicit_availability():
    explore_catalog = _load_explore_catalog_module()
    models = [
        {
            "slug": "nimble",
            "capabilities": ["decision", "tools", "thinking"],
            "modalities": ["text"],
            "availability": ["local"],
            "variants": [{"tag": "latest", "input": "Text", "modalities": ["text"], "availability": "local"}],
        },
        {
            "slug": "clef",
            "capabilities": ["decision", "vision"],
            "modalities": ["image", "text"],
            "availability": ["cloud"],
            "variants": [{"tag": "latest-cloud", "input": "Text, Image", "modalities": ["image", "text"], "availability": "cloud"}],
        },
        {
            "slug": "audio-model",
            "capabilities": ["audio"],
            "modalities": ["audio"],
            "availability": ["local"],
            "variants": [{"tag": "latest", "input": "Audio", "modalities": ["audio"], "availability": "local"}],
        },
        {
            "slug": "mixed-delivery",
            "capabilities": ["decision"],
            "modalities": ["text"],
            "availability": ["cloud", "local"],
            "variants": [
                {"tag": "latest", "input": "Text", "modalities": ["text"], "availability": "local"},
                {"tag": "large-cloud", "input": "Text", "modalities": ["text"], "availability": "cloud"},
            ],
        },
    ]

    assert [m["slug"] for m in explore_catalog.apply_filters(models, caps="decision")] == ["nimble", "clef", "mixed-delivery"]
    assert [m["slug"] for m in explore_catalog.apply_filters(models, modality="text,image")] == ["clef"]
    assert [m["slug"] for m in explore_catalog.apply_filters(models, modality="audio")] == ["audio-model"]
    assert [m["slug"] for m in explore_catalog.apply_filters(models, local_only=True)] == ["nimble", "audio-model", "mixed-delivery"]
    assert [m["slug"] for m in explore_catalog.apply_filters(models, cloud_only=True)] == ["clef"]


def test_filters_keep_legacy_tag_based_cloud_records():
    explore_catalog = _load_explore_catalog_module()
    models = [{"slug": "legacy-cloud", "variants": [{"tag": "latest-cloud"}]}]

    assert explore_catalog.apply_filters(models, cloud_only=True) == models


def test_show_list_displays_new_columns(capsys):
    explore_catalog = _load_explore_catalog_module()
    explore_catalog.console = Console(width=240)
    model = {
        "slug": "clef",
        "pulls": 1,
        "pulls_text": "1",
        "tags_count": 1,
        "capabilities": ["decision", "vision"],
        "modalities": ["image", "text"],
        "availability": ["cloud"],
        "updated": "today",
        "blurb": "decision model",
        "variants": [],
    }

    explore_catalog.show_list([model], limit=0)

    output = capsys.readouterr().out
    assert "Modalities" in output
    assert "Availability" in output
    assert "image text" in output
    assert "cloud" in output
