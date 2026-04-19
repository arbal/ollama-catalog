# Ollama Catalog

Ollama Catalog is a robust web scraper that extracts detailed information about both official and community models from the Ollama website. It acts as an open-source alternative and spiritual successor to `chrizzo84/OllamaScraper`, implementing a reliable, type-hinted, asynchronous pipeline.

*Inspired by [chrizzo84/OllamaScraper](https://github.com/chrizzo84/OllamaScraper).*
*Licensed under MIT.*

## Features vs. OllamaScraper
- **Asynchronous Processing**: Uses `httpx` and `asyncio` to crawl with bounded concurrency.
- **Support for Community Models**: Understands nested namespaces (`namespace/model`) introduced for community-created models.
- **Detailed Parsing**: Robust parsing of pulls/downloads, multiple capabilities (vision, tools, thinking, embedding), model variants, descriptions, and metadata.
- **Incremental Saves & Resiliency**: Periodic JSON flushing (every 50 models) to safeguard data during execution failures.

## Quick Start

```bash
git clone https://github.com/your-username/ollama-catalog.git
cd ollama-catalog
pip install -e .
ollama-catalog run
```

## Architecture

The project employs a **Two-Stage Pipeline**:
1. **Discovery Engine (`ollama-catalog discover`)**: Crawls the Ollama search via pagination across the alphanumeric alphabet. Note that because Ollama limits query pagination depth, this alphabet crawl is **best-effort and not guaranteed to be 100% exhaustive**.
2. **Detail Fetching (`ollama-catalog fetch`)**: Takes the newly discovered slugs and fetches exhaustive metadata for each by downloading their detail and tags pages.

### Git-as-Time-Series
We persist state exclusively to plain JSON files, notably `out/ollama_catalog.json` and `out/seen_slugs.json`. When deployed on a daily cron schedule via GitHub Actions (or the provided `scripts/daily-run.sh`), the git history becomes a queryable time-series database.

By utilizing diff tooling, you can analyze changes in model pull counts, new tags, and newly discovered models over time.

Example using a companion diff tool:
```bash
OLLAMASCRAPER_REPO=/path/to/ollama-catalog ollama-models-diff --days 7
```

## Command Reference

| Command | Flags | Description |
| :--- | :--- | :--- |
| `discover` | `--full`, `--dry-run`, `--limit N` | Crawl Ollama search to identify new model slugs. |
| `fetch` | `--refetch`, `--limit N`, `--concurrency N` | Download model metadata for discovered slugs. |
| `run` | *(Combines all above flags)* | Executes `discover` followed by `fetch`. This is the typical workflow for daily automation. |

### Explore the catalog

The repo also includes `oc-explore`, a local CLI wrapper around `scripts/explore_catalog.py` for slicing, trending, and comparing the scraped catalog data.

```bash
oc-explore --local-only --sort velocity
oc-explore --cloud-only --sort pulls-per-tag
oc-explore --namespace mistral --namespace-stats
oc-explore --namespace-stats huihui_ai
oc-explore --trending-namespace --namespace-stats
oc-explore --stale 180
oc-explore --catalog-history
oc-explore --history qwen3
oc-explore --format json --caps vision
```

Common usage patterns:
- Pullable models only: `oc-explore --local-only`
- Cloud-only registry entries: `oc-explore --cloud-only`
- Fastest-growing local models: `oc-explore --local-only --sort velocity`
- Publisher summary: `oc-explore --namespace mistral --namespace-stats`
- Friendlier publisher shorthand: `oc-explore --namespace-stats huihui_ai`
- Top trending publisher drill-down: `oc-explore --trending-namespace --namespace-stats`
- Stale models: `oc-explore --stale 180`
- Machine-readable export: `oc-explore --format json --local-only`

Chart / TUI views:
- `--history SLUG` — pull-count history for one model with a sparkline panel
- `--catalog-history` — catalog-wide pull totals over git history with a sparkline panel
- `--namespace-stats` — publisher summary table plus namespace pull-history sparkline

Notable explore modes:
- `--local-only` / `--cloud-only` — separate pullable models from cloud-only registry entries
- `--sort pulls-per-tag` — surface concentrated models with unusually high pulls per variant
- `--sort velocity` — rank models by pulls per day since their last update
- `--trending-namespace` — rank publishers by pull momentum vs a comparison ref
- `--namespace-stats` — summarize a publisher and list its models; accepts either `--namespace PATTERN --namespace-stats` or `--namespace-stats PATTERN`
- `--stale N` — filter to models not updated in `N+` days
- `--catalog-history` — show catalog-wide pull totals across git snapshots
- `--format json|tsv` — emit machine-readable output for scripting

`--format json|tsv` is intended for piping and automation; the sparkline/chart panels appear only in the TUI output.

Examples:
```bash
oc-explore --history qwen3
oc-explore --catalog-history
oc-explore --namespace-stats huihui_ai
oc-explore --trending-namespace --namespace-stats
oc-explore --format tsv --stale 365
```

If `--namespace-stats` is used together with `--trending-namespace`, `oc-explore` automatically drills into the top trending namespace for the current comparison window.

## Output Schema

The output generated in `out/ollama_catalog.json` has the following schema:
```json
{
  "scraped_at": "ISO8601 Timestamp",
  "model_count": 1234,
  "models": [
    {
      "slug": "llama2",
      "name": "llama2",
      "model_type": "official",
      "namespace": null,
      "pulls": 6600000,
      "pulls_text": "6.6M",
      "capabilities": ["tools", "vision"],
      "blurb": "Short text",
      "description": "Long text...",
      "updated": "2 years ago",
      "tags_count": 3,
      "variants": [
        {
          "tag": "latest",
          "size_bytes": 4026531840,
          "size_text": "3.8 GB",
          "context": "",
          "input": ""
        }
      ]
    }
  ]
}
```

## Known Limitations
- Since the discovery crawler uses single alphanumeric character queries (`a-z`, `0-9`) to bypass search limitations, it might miss some models if an alphabet subset exceeds the maximum pagination limit.
