import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx
from rich.progress import Progress, TaskID

from .model_scraper import ModelScraper
from .sanitization import SanitizationResult, sanitize_model_record, sanitize_models_jsonl
from .state import STATE_FILE

CATALOG_FILE = Path("out/ollama_catalog.json")
DISCOVERED_FILE = Path("out/discovered_slugs.json")

# Git-committed split files (small diffs, time-series friendly)
MODELS_JSONL   = Path("out/models.jsonl")
PULLS_JSONL    = Path("out/pulls.jsonl")
METADATA_JSON  = Path("out/metadata.json")
SEEN_SLUGS_FILE = STATE_FILE

# Fields committed to models.jsonl (stable — only changes on structural updates)
_STABLE_FIELDS = ["slug", "name", "model_type", "namespace", "capabilities",
                   "blurb", "description", "updated", "tags_count", "variants"]

class CatalogFetcher:
    def __init__(self, concurrency: int = 10):
        self.concurrency = concurrency
        self.semaphore = asyncio.Semaphore(concurrency)
        self.client = httpx.AsyncClient(
            http2=True,
            follow_redirects=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ollama-catalog/1.0)"},
            timeout=30.0
        )
        self.scraper = ModelScraper(client=self.client)
        self.models: Dict[str, Dict[str, Any]] = {}
        self.processed_count = 0
        self.total_count = 0

    def load_discovered(self) -> List[str]:
        if not DISCOVERED_FILE.exists():
            raise FileNotFoundError(
                f"{DISCOVERED_FILE} not found. Run 'ollama-catalog discover' first."
            )
        try:
            with open(DISCOVERED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def load_existing_catalog(self) -> Dict[str, Any]:
        # Primary: full JSON (fast local working file)
        if CATALOG_FILE.exists():
            try:
                with open(CATALOG_FILE, "r", encoding="utf-8") as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                pass
        # Fallback: reconstruct from committed JSONL split files
        if MODELS_JSONL.exists() and PULLS_JSONL.exists():
            models: Dict[str, Any] = {}
            with open(MODELS_JSONL, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        m = json.loads(line)
                        models[m["slug"]] = m
            with open(PULLS_JSONL, "r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if line:
                        p = json.loads(line)
                        if p["slug"] in models:
                            models[p["slug"]].update(p)
            return {"scraped_at": None, "model_count": len(models), "models": list(models.values())}
        return {"scraped_at": None, "model_count": 0, "models": []}

    def save_catalog(self):
        CATALOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        sorted_models = sorted([sanitize_model_record(m) for m in self.models.values() if m is not None], key=lambda x: x["slug"])
        scraped_at = datetime.now(timezone.utc).isoformat()

        # Local working file (not committed — derived from split files)
        output = {
            "scraped_at": scraped_at,
            "model_count": len(sorted_models),
            "models": sorted_models
        }
        with open(CATALOG_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)

        # Committed split files (git-friendly, small diffs)
        self._save_split(sorted_models, scraped_at)

    def _save_split(self, sorted_models: List[Dict[str, Any]], scraped_at: str):
        out_dir = MODELS_JSONL.parent
        out_dir.mkdir(parents=True, exist_ok=True)

        with open(MODELS_JSONL, "w", encoding="utf-8") as mf, \
             open(PULLS_JSONL,  "w", encoding="utf-8") as pf:
            for m in sorted_models:
                stable = {k: m[k] for k in _STABLE_FIELDS if k in m}
                if "capabilities" in stable:
                    stable["capabilities"] = sorted(stable["capabilities"])
                mf.write(json.dumps(stable, separators=(',', ':')) + "\n")
                pf.write(json.dumps(
                    {"slug": m["slug"], "pulls": m.get("pulls", 0), "pulls_text": m.get("pulls_text", "0")},
                    separators=(',', ':')
                ) + "\n")

        with open(METADATA_JSON, "w", encoding="utf-8") as f:
            json.dump({"scraped_at": scraped_at, "model_count": len(sorted_models)}, f, indent=2)

    def sanitize_committed_models(self) -> SanitizationResult:
        """Redact existing public model text without changing scrape metadata."""
        return sanitize_models_jsonl(MODELS_JSONL)

    async def _fetch_and_process(self, slug: str, progress: Progress, task_id: TaskID) -> None:
        async with self.semaphore:
            model_data = await self.scraper.fetch_model_detail(slug)

            if model_data:
                self.models[slug] = model_data

            self.processed_count += 1

            # Incremental save
            if self.processed_count % 50 == 0:
                self.save_catalog()

            status = "OK" if model_data else "Failed/404"
            pulls = model_data["pulls_text"] if model_data else "-"
            caps = ",".join(model_data["capabilities"]) if model_data else "-"

            progress.update(
                task_id,
                advance=1,
                description=f"Fetching {self.processed_count}/{self.total_count}: {slug} | {status} | {pulls} | {caps}"
            )

    async def run(
        self,
        limit: Optional[int] = None,
        refetch: bool = False,
        reconcile: bool = False,
    ):
        if reconcile and not refetch:
            raise ValueError("reconcile requires refetch")
        existing = self.load_existing_catalog()
        # Always pre-load existing catalog models so incremental saves don't lose data
        self.models = {m["slug"]: m for m in existing.get("models", []) if m is not None}

        if reconcile:
            seen_file = SEEN_SLUGS_FILE
            if not seen_file.exists():
                raise FileNotFoundError(
                    "out/seen_slugs.json is required for reconciliation. "
                    "Run 'ollama-catalog discover --full' first."
                )
            with open(seen_file, "r", encoding="utf-8") as f:
                authoritative_slugs = set(json.load(f))
            if not authoritative_slugs:
                raise ValueError("Refusing to reconcile against an empty seen-slug set.")
            self.models = {
                slug: model for slug, model in self.models.items()
                if slug in authoritative_slugs
            }

        slugs_to_fetch_set = set()

        if refetch:
            # If refetching, get everything from existing catalog, discovered, and seen.
            # In reconciliation mode, the full discovery just replaced seen with
            # the authoritative upstream listing, so stale records are excluded.
            slugs_to_fetch_set.update(self.models.keys())
            try:
                slugs_to_fetch_set.update(self.load_discovered())
            except FileNotFoundError:
                pass  # OK in refetch mode — catalog slugs already loaded above

            seen_file = SEEN_SLUGS_FILE
            if seen_file.exists():
                try:
                    with open(seen_file, "r", encoding="utf-8") as f:
                        slugs_to_fetch_set.update(json.load(f))
                except Exception:
                    pass
        else:
            # Normal workflow: just fetch discovered slugs that aren't refetching
            slugs_to_fetch_set.update(self.load_discovered())

        # Sort the slugs for deterministic processing
        slugs_to_fetch = sorted(list(slugs_to_fetch_set))

        if limit:
            slugs_to_fetch = slugs_to_fetch[:limit]

        self.total_count = len(slugs_to_fetch)

        with Progress() as progress:
            task_id = progress.add_task("Fetching models...", total=self.total_count)
            tasks = [self._fetch_and_process(slug, progress, task_id) for slug in slugs_to_fetch]
            await asyncio.gather(*tasks)

        if self.processed_count > 0:
            self.save_catalog()
        await self.client.aclose()
