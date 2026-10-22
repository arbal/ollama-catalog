#!/usr/bin/env python3
"""
Reconstruct full ollama_catalog.json from the git-committed JSONL split files.

The canonical committed format is:
  out/models.jsonl  — stable structural data (slug, variants, capabilities, etc.)
  out/pulls.jsonl   — volatile pull counts (slug, pulls, pulls_text)
  out/metadata.json — scraped_at, model_count

This script merges them back into the full catalog JSON at any point in git history.

Usage:
  python3 scripts/render_catalog.py                       # current files → out/ollama_catalog.json
  python3 scripts/render_catalog.py HEAD~7                # 7 commits ago
  python3 scripts/render_catalog.py abc1234               # specific commit hash
  python3 scripts/render_catalog.py 2026-04-01            # date (resolves to nearest commit)
  python3 scripts/render_catalog.py HEAD~7 -o catalog.json
  python3 scripts/render_catalog.py HEAD -o -             # write to stdout
"""
import argparse
import json
import re
import subprocess
import sys
from pathlib import Path


def git_show(ref: str, path: str) -> str:
    if ref.startswith("-"):
        raise ValueError(f"Invalid git ref: {ref}")
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        capture_output=True, text=True, check=True
    )
    return result.stdout


def resolve_date(date_str: str) -> str:
    """Resolve YYYY-MM-DD to the most recent commit hash on or before that date."""
    result = subprocess.run(
        ["git", "log", f"--before={date_str} 23:59:59", "-1", "--format=%H"],
        capture_output=True, text=True, check=True
    )
    commit = result.stdout.strip()
    if not commit:
        raise SystemExit(f"error: no commits found on or before {date_str}")
    return commit


def load_from_files(models_path: Path, pulls_path: Path, metadata_path: Path):
    models: dict = {}
    with open(models_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                m = json.loads(line)
                models[m["slug"]] = m
    with open(pulls_path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                p = json.loads(line)
                if p["slug"] in models:
                    models[p["slug"]]["pulls"] = p["pulls"]
                    models[p["slug"]]["pulls_text"] = p["pulls_text"]
    metadata = {}
    if metadata_path.exists():
        with open(metadata_path, encoding="utf-8") as f:
            metadata = json.load(f)
    return models, metadata


def load_from_git(ref: str):
    models: dict = {}
    for line in git_show(ref, "out/models.jsonl").splitlines():
        line = line.strip()
        if line:
            m = json.loads(line)
            models[m["slug"]] = m
    for line in git_show(ref, "out/pulls.jsonl").splitlines():
        line = line.strip()
        if line:
            p = json.loads(line)
            if p["slug"] in models:
                models[p["slug"]]["pulls"] = p["pulls"]
                models[p["slug"]]["pulls_text"] = p["pulls_text"]
    try:
        metadata = json.loads(git_show(ref, "out/metadata.json"))
    except subprocess.CalledProcessError:
        metadata = {}
    return models, metadata


def render(models: dict, metadata: dict) -> dict:
    sorted_models = sorted(models.values(), key=lambda x: x["slug"])
    return {
        "scraped_at": metadata.get("scraped_at"),
        "model_count": len(sorted_models),
        "models": sorted_models,
    }


def main():
    parser = argparse.ArgumentParser(
        description="Render full ollama_catalog.json from committed JSONL split files",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Usage:")[1].strip() if "Usage:" in __doc__ else ""
    )
    parser.add_argument(
        "ref", nargs="?", default=None,
        help="Git ref (commit hash, HEAD~N) or date (YYYY-MM-DD). Omit for current files."
    )
    parser.add_argument(
        "--output", "-o", default=None,
        help="Output path. Use '-' for stdout. Default: out/ollama_catalog.json"
    )
    args = parser.parse_args()

    if args.ref is None:
        models, metadata = load_from_files(
            Path("out/models.jsonl"),
            Path("out/pulls.jsonl"),
            Path("out/metadata.json"),
        )
    else:
        ref = args.ref
        if re.match(r"^\d{4}-\d{2}-\d{2}$", ref):
            ref = resolve_date(ref)
            print(f"Resolved {args.ref} → {ref[:12]}...", file=sys.stderr)
        models, metadata = load_from_git(ref)

    catalog = render(models, metadata)
    output = args.output or "out/ollama_catalog.json"

    if output == "-":
        json.dump(catalog, sys.stdout, indent=2)
        sys.stdout.write("\n")
    else:
        Path(output).parent.mkdir(parents=True, exist_ok=True)
        with open(output, "w", encoding="utf-8") as f:
            json.dump(catalog, f, indent=2)
        print(f"Rendered {catalog['model_count']} models → {output}", file=sys.stderr)


if __name__ == "__main__":
    main()
