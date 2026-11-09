import importlib.util
from pathlib import Path

import pytest


def _load_render_catalog_module():
    script = Path(__file__).parents[1] / "scripts" / "render_catalog.py"
    spec = importlib.util.spec_from_file_location("render_catalog", script)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_git_show_rejects_refs_that_git_would_parse_as_options():
    render_catalog = _load_render_catalog_module()
    with pytest.raises(SystemExit, match="must not start with '-'"):
        render_catalog.git_show("--output=/tmp/should-not-write", "out/models.jsonl")
