# AGENTS.md — ollama-catalog

Scraper that builds a structured JSON catalog of all Ollama models (official + community).

## Private Operational Companion

This public repository contains public-safe code guidance only. Authorized
local operational work uses the separately versioned companion spec at
`/root/agent-shared/ollama-catalog/AGENTS.md`.

Never create, read as canonical, or write lifecycle plans or other operational
artifacts under `/root/ollama-catalog/.agent`. Store ollama-catalog lifecycle
run artifacts only under `/root/agent-shared/.runs/ollama-catalog/<UTC_TIMESTAMP>/`.

Before committing or pushing generated public catalog data, run
`scripts/check-public-catalog.sh`. Install its local Git hooks with
`scripts/install-public-git-hooks.sh`; the hooks validate that all generated
files are present, parse as JSON, and contain only constrained public model
identifiers. The daily Catalog Update workflow intentionally does not run a
credential-pattern scanner over upstream model text: broad heuristic matches
on public model names and documentation previously blocked catalog publishing.

## Architecture

Two-stage pipeline:

```
discover  →  out/discovered_slugs.json  →  fetch  →  out/ollama_catalog.json
                                             ↑
                                     out/seen_slugs.json  (current full-listing state)
```

### Modules

| File | Role |
|---|---|
| `src/ollama_catalog/scraper.py` | `DiscoveryScraper` — alphabet crawl of `ollama.com/search?q=X&o=newest`, extracts slugs via regex, with incremental and complete-coverage modes |
| `src/ollama_catalog/model_scraper.py` | `ModelScraper` — fetches `ollama.com/{slug}` + `ollama.com/{slug}/tags`, parses pulls/caps/variants/blurb |
| `src/ollama_catalog/catalog.py` | `CatalogFetcher` — drives concurrent detail fetches, incremental JSON saves every 50 models |
| `src/ollama_catalog/state.py` | `StateManager` — persists `seen_slugs.json`, provides `is_seen()` / `merge()` |
| `src/ollama_catalog/cli.py` | CLI entrypoint: `discover`, `fetch`, `run` subcommands |
| `scripts/daily-run.sh` | Cron-friendly wrapper that runs `discover` then `fetch` |

### Output files (`out/`)

| File | Description |
|---|---|
| `discovered_slugs.json` | All slugs found in current discovery run (input to `fetch`) |
| `seen_slugs.json` | Incremental crawl state; a successful `discover --full` replaces it with the current authoritative search listing |
| `ollama_catalog.json` | Final catalog — `scraped_at`, `model_count`, `models[]` |

### Catalog model schema

```json
{
  "slug": "namespace/model-name",
  "name": "model-name",
  "model_type": "community",
  "namespace": "namespace",
  "pulls": 12000,
  "pulls_text": "12K",
  "capabilities": ["tools", "vision"],
  "blurb": "Short description from meta tag",
  "description": "Full readme text",
  "updated": "3 days ago",
  "tags_count": 4,
  "variants": [
    { "tag": "latest", "size_bytes": 4700000000, "size_text": "4.7 GB", "context": "", "input": "" }
  ]
}
```

`model_type` is `"official"` for models without a `/` in the slug (e.g. `llama3.2`), `"community"` otherwise.

## Development Setup

```bash
python3 -m venv .venv
.venv/bin/pip install -e ".[dev]"
```

## CLI Usage

```bash
# Discover newly unknown slugs with the fast incremental crawl
.venv/bin/ollama-catalog discover

# Discover with limit for testing
.venv/bin/ollama-catalog discover --limit 50

# Fetch model details for all discovered slugs
.venv/bin/ollama-catalog fetch

# Fetch with custom concurrency
.venv/bin/ollama-catalog fetch --concurrency 20

# One-shot: discover + fetch
.venv/bin/ollama-catalog run

# Refetch everything (ignores seen state)
.venv/bin/ollama-catalog fetch --refetch
# Reconcile catalog membership to a successful full upstream listing
.venv/bin/ollama-catalog discover --full
.venv/bin/ollama-catalog fetch --refetch --reconcile
```

## Key Implementation Details

### Discovery — incremental stop

`DiscoveryScraper` uses `StateManager.incremental_stop` (default 3): if 3 consecutive pages for a query contain only already-seen slugs, incremental crawling stops for that query. This makes ad-hoc re-runs fast, but it cannot prove that no unseen URLs occur later in the search results.

Use `--full` for a complete listing reconciliation. It crawls every result page using the upstream HTMX pagination protocol, but still writes only slugs absent from `seen_slugs.json` to the discovery output. It fails rather than replacing state if it extracts no model links. The scheduled GitHub workflow follows it with `fetch --refetch --reconcile`, which removes catalog records absent from the successful full listing. This prevents a changed search ordering, stale HTML selector, or obsolete model URL from silently producing a false zero-addition update.

### Fetch — crash recovery

`CatalogFetcher` writes the catalog every 50 processed models. If the process is killed, the partial catalog is preserved and a re-run skips already-fetched slugs (they're already in the catalog dict loaded at startup).

### HTTP client

All three scrapers use `httpx.AsyncClient` with:
- `http2=True`
- `follow_redirects=True` — required because ollama.com redirects lowercase namespace URLs to their canonical casing (e.g. `zero9tech/` → `Zero9Tech/`)
- `timeout=30.0`

`ModelScraper._fetch_url` has a tenacity retry (3 attempts, exponential backoff) for transient `httpx.RequestError`s. 404s pass through immediately and return `None`.

### Discovery — URL pattern

```
https://ollama.com/search?q={letter}&o=newest&page={n}
```

Blank `q=` returns only ~219 official models. The alphabet crawl (`a-z` + `0-9`) is required to surface community models. Full-text search means a model may appear under multiple query letters; dedup is handled by the `discovered_slugs` set.

Slug extraction regex: `x-test-search-response-title[^>]*>\s*([^<]+?)\s*<`

## Tests

```bash
.venv/bin/pytest tests/
```

| Test file | Covers |
|---|---|
| `tests/test_discovery.py` | Dedup, incremental stop, limit |
| `tests/test_model_scraper.py` | URL detection, pulls parsing, variants, 404, success |
| `tests/test_catalog.py` | Catalog load/save behavior |

GitHub Actions runs the full test suite through `.github/workflows/test.yml`
on pushes to `main` and on pull requests. This is separate from the scheduled
catalog update workflow.

## Daily Automation

`scripts/daily-run.sh` is designed for cron. Run from the repo root:

```bash
cd /path/to/ollama-catalog && bash scripts/daily-run.sh
```

On each run it discovers new models since last run, fetches their details, and appends them to the catalog.
