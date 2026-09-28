#!/usr/bin/env python3
"""Produce deterministic, joined catalog snapshot comparisons.

This helper emits machine-readable JSON only. Narrative reports belong in the
private operational companion and must use the split-artifact join by slug.
"""

from __future__ import annotations

import argparse
import json
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


ARTIFACTS = ("models.jsonl", "pulls.jsonl", "metadata.json")


def parse_jsonl(content: str, artifact: str) -> list[dict[str, Any]]:
    rows = []
    for line_number, line in enumerate(content.splitlines(), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"invalid JSON in {artifact}:{line_number}") from exc
        if not isinstance(row, dict) or not row.get("slug"):
            raise ValueError(f"missing slug in {artifact}:{line_number}")
        rows.append(row)
    return rows


def index_unique(rows: list[dict[str, Any]], artifact: str) -> dict[str, dict[str, Any]]:
    indexed = {}
    for row in rows:
        slug = row["slug"]
        if slug in indexed:
            raise ValueError(f"duplicate slug in {artifact}: {slug}")
        indexed[slug] = row
    return indexed


def build_snapshot(
    models_content: str,
    pulls_content: str,
    metadata_content: str,
) -> dict[str, Any]:
    models = index_unique(parse_jsonl(models_content, "models.jsonl"), "models.jsonl")
    pulls = index_unique(parse_jsonl(pulls_content, "pulls.jsonl"), "pulls.jsonl")
    metadata = json.loads(metadata_content)
    if not isinstance(metadata, dict):
        raise ValueError("metadata.json must contain an object")

    missing_pulls = sorted(set(models) - set(pulls))
    orphan_pulls = sorted(set(pulls) - set(models))
    if missing_pulls or orphan_pulls:
        raise ValueError(
            "model/pull slug mismatch: "
            f"missing_pulls={len(missing_pulls)} orphan_pulls={len(orphan_pulls)}"
        )

    return {"models": models, "pulls": pulls, "metadata": metadata}


def _pulls(snapshot: dict[str, Any], slug: str) -> int:
    return int(snapshot["pulls"][slug].get("pulls") or 0)


def _field_changes(
    baseline: dict[str, Any], current: dict[str, Any], common: set[str]
) -> tuple[Counter[str], int]:
    counts: Counter[str] = Counter()
    changed_records = 0
    for slug in common:
        changed = False
        keys = set(baseline["models"][slug]) | set(current["models"][slug])
        for key in keys:
            if key in {"pulls", "pulls_text"}:
                continue
            if baseline["models"][slug].get(key) != current["models"][slug].get(key):
                counts[key] += 1
                changed = True
        changed_records += changed
    return counts, changed_records


def compare_snapshots(baseline: dict[str, Any], current: dict[str, Any]) -> dict[str, Any]:
    baseline_slugs = set(baseline["models"])
    current_slugs = set(current["models"])
    added = sorted(current_slugs - baseline_slugs)
    removed = sorted(baseline_slugs - current_slugs)
    common = baseline_slugs & current_slugs
    field_changes, changed_records = _field_changes(baseline, current, common)

    growth = []
    for slug in common:
        old = _pulls(baseline, slug)
        new = _pulls(current, slug)
        if old != new:
            growth.append({"slug": slug, "old": old, "new": new, "delta": new - old})
    growth.sort(key=lambda row: (row["delta"], row["slug"]), reverse=True)

    added_pull_bands = Counter()
    added_rows = []
    for slug in added:
        pulls = _pulls(current, slug)
        if pulls == 0:
            band = "0"
        elif pulls < 100:
            band = "1-99"
        elif pulls < 1000:
            band = "100-999"
        else:
            band = "1000+"
        added_pull_bands[band] += 1
        added_rows.append(
            {
                "slug": slug,
                "pulls": pulls,
                "model_type": current["models"][slug].get("model_type"),
                "capabilities": current["models"][slug].get("capabilities") or [],
            }
        )
    added_rows.sort(key=lambda row: (row["pulls"], row["slug"]), reverse=True)

    capabilities = Counter()
    for row in (current["models"][slug] for slug in added):
        capabilities.update(row.get("capabilities") or [])

    baseline_total = sum(_pulls(baseline, slug) for slug in baseline["pulls"])
    current_total = sum(_pulls(current, slug) for slug in current["pulls"])
    return {
        "baseline": baseline["metadata"],
        "current": current["metadata"],
        "counts": {
            "baseline_models": len(baseline_slugs),
            "current_models": len(current_slugs),
            "added": len(added),
            "removed": len(removed),
            "common": len(common),
            "changed_continuing_records": changed_records,
        },
        "pulls": {
            "baseline_total": baseline_total,
            "current_total": current_total,
            "delta": current_total - baseline_total,
            "added_pull_bands": dict(sorted(added_pull_bands.items())),
            "top_absolute_growth": growth[:25],
        },
        "added": {
            "top_by_pulls": added_rows[:25],
            "capabilities": dict(capabilities.most_common()),
        },
        "field_changes": dict(field_changes.most_common()),
        "removed_slugs": removed,
    }


def _git_show(ref: str, path: str, repo: Path) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), "show", f"{ref}:out/{path}"],
        check=True,
        capture_output=True,
        text=True,
    ).stdout


def load_ref(ref: str, repo: Path) -> dict[str, Any]:
    return build_snapshot(
        _git_show(ref, "models.jsonl", repo),
        _git_show(ref, "pulls.jsonl", repo),
        _git_show(ref, "metadata.json", repo),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", required=True, help="baseline git ref")
    parser.add_argument("--current", default="HEAD", help="current git ref")
    parser.add_argument("--repo", type=Path, default=Path.cwd())
    args = parser.parse_args()
    result = compare_snapshots(load_ref(args.baseline, args.repo), load_ref(args.current, args.repo))
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
