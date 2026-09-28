import importlib.util
from pathlib import Path

import pytest


def _load_module():
    path = Path(__file__).parents[1] / "scripts" / "catalog_intelligence.py"
    spec = importlib.util.spec_from_file_location("catalog_intelligence", path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _snapshot(module, models, pulls):
    return module.build_snapshot(
        "\n".join(__import__("json").dumps(row) for row in models),
        "\n".join(__import__("json").dumps(row) for row in pulls),
        '{"scraped_at":"2026-09-28T00:00:00Z","model_count":2}',
    )


def test_comparison_joins_pull_artifact_by_slug():
    module = _load_module()
    baseline = _snapshot(
        module,
        [{"slug": "library/base", "model_type": "official"}],
        [{"slug": "library/base", "pulls": 10, "pulls_text": "10"}],
    )
    current = _snapshot(
        module,
        [
            {"slug": "library/base", "model_type": "official", "updated": "today"},
            {"slug": "new/model", "model_type": "community", "capabilities": ["tools"]},
        ],
        [
            {"slug": "library/base", "pulls": 25, "pulls_text": "25"},
            {"slug": "new/model", "pulls": 7, "pulls_text": "7"},
        ],
    )

    result = module.compare_snapshots(baseline, current)

    assert result["counts"] == {
        "baseline_models": 1,
        "current_models": 2,
        "added": 1,
        "removed": 0,
        "common": 1,
        "changed_continuing_records": 1,
    }
    assert result["pulls"]["baseline_total"] == 10
    assert result["pulls"]["current_total"] == 32
    assert result["pulls"]["delta"] == 22
    assert result["added"]["top_by_pulls"][0]["pulls"] == 7
    assert result["field_changes"] == {"updated": 1}


@pytest.mark.parametrize(
    "models,pulls,match",
    [
        ([{"slug": "one"}, {"slug": "one"}], [{"slug": "one"}], "duplicate slug in models.jsonl"),
        ([{"slug": "one"}], [{"slug": "one"}, {"slug": "one"}], "duplicate slug in pulls.jsonl"),
        ([{"slug": "one"}], [{"slug": "other"}], "model/pull slug mismatch"),
    ],
)
def test_split_artifact_contract_rejects_invalid_joins(models, pulls, match):
    module = _load_module()
    with pytest.raises(ValueError, match=match):
        _snapshot(module, models, pulls)
