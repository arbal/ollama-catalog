#!/bin/sh

# Exit immediately if a command exits with a non-zero status.
set -e

echo "Starting daily catalog update..."
ollama-catalog discover --full
ollama-catalog fetch --refetch --reconcile
ollama-catalog sanitize
scripts/check-public-catalog.sh

echo "Committing updates..."
git add out/models.jsonl out/pulls.jsonl out/metadata.json out/seen_slugs.json out/discovered_slugs.json
if git diff --cached --quiet; then
  echo "No changes to commit."
else
  git commit -m "chore: catalog update $(date -u +%Y-%m-%dT%H:%M:%SZ)"
fi

echo "Daily run complete."
