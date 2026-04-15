import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Dict, Any, Optional
import httpx
from rich.progress import Progress, TaskID

from .model_scraper import ModelScraper

CATALOG_FILE = Path("out/ollama_catalog.json")
DISCOVERED_FILE = Path("out/discovered_slugs.json")

class CatalogFetcher:
    def __init__(self, concurrency: int = 10):
        self.concurrency = concurrency
        self.semaphore = asyncio.Semaphore(concurrency)
        self.client = httpx.AsyncClient(
            http2=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ollama-catalog/1.0)"},
            timeout=30.0
        )
        self.scraper = ModelScraper(client=self.client)
        self.models: List[Dict[str, Any]] = []
        self.processed_count = 0
        self.total_count = 0

    def load_discovered(self) -> List[str]:
        if not DISCOVERED_FILE.exists():
            return []
        try:
            with open(DISCOVERED_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []

    def load_existing_catalog(self) -> Dict[str, Any]:
        if not CATALOG_FILE.exists():
            return {"scraped_at": None, "model_count": 0, "models": []}
        try:
            with open(CATALOG_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return {"scraped_at": None, "model_count": 0, "models": []}

    def save_catalog(self):
        CATALOG_FILE.parent.mkdir(parents=True, exist_ok=True)
        # Deduplicate and sort
        models_by_slug = {m["slug"]: m for m in self.models if m is not None}
        sorted_models = sorted(models_by_slug.values(), key=lambda x: x["slug"])

        output = {
            "scraped_at": datetime.now(timezone.utc).isoformat(),
            "model_count": len(sorted_models),
            "models": sorted_models
        }

        with open(CATALOG_FILE, "w", encoding="utf-8") as f:
            json.dump(output, f, indent=2)

    async def _fetch_and_process(self, slug: str, progress: Progress, task_id: TaskID) -> None:
        async with self.semaphore:
            model_data = await self.scraper.fetch_model_detail(slug)

            if model_data:
                self.models.append(model_data)

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

    async def run(self, limit: Optional[int] = None, refetch: bool = False):
        slugs_to_fetch = self.load_discovered()

        if not refetch:
            existing = self.load_existing_catalog()
            existing_slugs = {m["slug"] for m in existing.get("models", [])}
            # Keep existing models that we aren't refetching
            self.models = [m for m in existing.get("models", []) if m["slug"] not in slugs_to_fetch]

            # Filter slugs to only those not already in catalog, IF not refetching everything
            # The requirement: "Load out/discovered_slugs.json unless --refetch"
            # Actually, if --refetch is true, we re-fetch all in discovered_slugs.json (and potentially seen_slugs?
            # Re-read requirements: Load out/discovered_slugs.json (written by discover command) unless --refetch
            # If refetch, we likely want to refetch everything we know about.
            # But "written by discover command" implies discover outputs what's new.
            # Let's just fetch whatever is in discovered_slugs.json. If not refetch, maybe skip existing ones.
            # Requirement: Load out/discovered_slugs.json (written by discover command) unless --refetch)
            # This is slightly ambiguous: "Load out/discovered_slugs.json unless --refetch".
            # What do we load if --refetch? out/seen_slugs.json?
            if refetch:
                # Load ALL seen slugs
                seen_file = Path("out/seen_slugs.json")
                if seen_file.exists():
                    try:
                        with open(seen_file, "r", encoding="utf-8") as f:
                            slugs_to_fetch = json.load(f)
                    except Exception:
                        pass
                self.models = [] # Start fresh
            else:
                # Only fetch discovered ones, keep existing ones in catalog
                pass

        if limit:
            slugs_to_fetch = slugs_to_fetch[:limit]

        self.total_count = len(slugs_to_fetch)

        with Progress() as progress:
            task_id = progress.add_task("Fetching models...", total=self.total_count)
            tasks = [self._fetch_and_process(slug, progress, task_id) for slug in slugs_to_fetch]
            await asyncio.gather(*tasks)

        self.save_catalog()
        await self.client.aclose()
