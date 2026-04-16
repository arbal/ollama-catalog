#!/bin/sh

# Exit immediately if a command exits with a non-zero status.
set -e

echo "Starting daily catalog update..."
ollama-catalog run

echo "Committing updates..."
git add out/ollama_catalog.json out/seen_slugs.json out/discovered_slugs.json 2>/dev/null || true
git commit -m "chore: catalog update $(date -u +%Y-%m-%dT%H:%M:%SZ)" || echo "No changes to commit."

echo "Daily run complete."
