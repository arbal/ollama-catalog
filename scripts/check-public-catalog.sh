#!/usr/bin/env bash
set -euo pipefail

# This gate deliberately validates generated catalog structure only.  Catalog
# descriptions are public, upstream-controlled text; secret scanners have
# repeatedly treated ordinary model names and prose as credentials and blocked
# the daily publish job.  Repository code is covered by the normal Test
# workflow, while this workflow must reliably publish the public catalog.
readonly public_catalog_artifacts=(
  out/models.jsonl
  out/pulls.jsonl
  out/metadata.json
  out/seen_slugs.json
  out/discovered_slugs.json
)

validate_artifacts() {
  python3 - "${public_catalog_artifacts[@]}" <<'PY'
import json
import re
import sys
from pathlib import Path

artifacts = [Path(value) for value in sys.argv[1:]]
slug_pattern = re.compile(r"^[A-Za-z0-9._-]+(?:/[A-Za-z0-9._-]+)?$")

def require_slug(value, source):
    if not isinstance(value, str) or not slug_pattern.fullmatch(value):
        raise SystemExit(f"invalid public model identifier in {source}")

for artifact in artifacts:
    if not artifact.is_file():
        raise SystemExit(f"missing generated catalog artifact: {artifact}")
    if artifact.name in {"models.jsonl", "pulls.jsonl"}:
        with artifact.open(encoding="utf-8") as source:
            for line_number, line in enumerate(source, 1):
                record = json.loads(line)
                if not isinstance(record, dict):
                    raise SystemExit(f"invalid JSON record in {artifact}:{line_number}")
                require_slug(record.get("slug"), f"{artifact}:{line_number}")
    elif artifact.name in {"seen_slugs.json", "discovered_slugs.json"}:
        values = json.loads(artifact.read_text(encoding="utf-8"))
        if not isinstance(values, list):
            raise SystemExit(f"invalid public model identifier list in {artifact}")
        for value in values:
            require_slug(value, artifact)
    else:
        json.loads(artifact.read_text(encoding="utf-8"))
PY
}

case "${1:-artifacts}" in
  artifacts)
    validate_artifacts
    ;;
  --staged-artifacts)
    for artifact in "${public_catalog_artifacts[@]}"; do
      git diff --quiet -- "$artifact" || {
        echo "staged artifact differs from working tree: $artifact" >&2
        exit 1
      }
    done
    validate_artifacts
    ;;
  --staged)
    # Retained for installed pre-commit hooks: catalog validation only.
    validate_artifacts
    ;;
  *)
    echo "usage: $0 [artifacts|--staged|--staged-artifacts]" >&2
    exit 2
    ;;
esac
