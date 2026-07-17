#!/usr/bin/env bash
set -euo pipefail

if ! command -v gitleaks >/dev/null 2>&1; then
  echo "gitleaks is required to scan public catalog content" >&2
  exit 2
fi

readonly public_catalog_artifacts=(
  out/models.jsonl
  out/pulls.jsonl
  out/metadata.json
  out/seen_slugs.json
  out/discovered_slugs.json
)

case "${1:-artifacts}" in
  artifacts)
    for artifact in "${public_catalog_artifacts[@]}"; do
      gitleaks dir --no-banner --no-color --redact=100 "$artifact"
    done
    ;;
  --staged)
    gitleaks git --staged --no-banner --no-color --redact=100
    ;;
  *)
    echo "usage: $0 [artifacts|--staged]" >&2
    exit 2
    ;;
esac
