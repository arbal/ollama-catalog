import asyncio
import re
import string
from typing import Set, List, Optional
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from rich.progress import Progress, TaskID

from .state import StateManager

class DiscoveryScraper:
    def __init__(self, state_manager: StateManager, limit: Optional[int] = None, full_mode: bool = False, dry_run: bool = False):
        self.state = state_manager
        self.limit = limit
        self.full_mode = full_mode
        self.dry_run = dry_run

        self.discovered_slugs: Set[str] = set()
        self.semaphore = asyncio.Semaphore(5)
        self.client = httpx.AsyncClient(
            http2=True,
            headers={"User-Agent": "Mozilla/5.0 (compatible; ollama-catalog/1.0)"},
            timeout=30.0
        )
        self.queries = list(string.ascii_lowercase + string.digits)
        self.stop_event = asyncio.Event()

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=6.0),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError))
    )
    async def _fetch_page(self, query: str, page: int) -> str:
        url = f"https://ollama.com/search?q={query}&o=newest&page={page}"
        async with self.semaphore:
            response = await self.client.get(url)
            response.raise_for_status()
            await asyncio.sleep(0.3)
            return response.text

    def _parse_slugs(self, html: str) -> List[str]:
        # Parse slugs using regex as requested
        return re.findall(r'x-test-search-response-title[^>]*>\s*([^<]+?)\s*<', html)

    async def _crawl_query(self, query: str, progress: Progress, task_id: TaskID):
        page = 1
        consecutive_empty_or_seen_pages = 0

        while not self.stop_event.is_set():
            try:
                html = await self._fetch_page(query, page)
            except Exception as e:
                # Log error or handle it. For now, stop crawling this query.
                break

            slugs = self._parse_slugs(html)

            if not slugs:
                break # Empty page, done with this query

            new_slugs_in_page = 0
            for slug in slugs:
                if self.stop_event.is_set():
                    break

                is_seen = self.state.is_seen(slug)
                if not self.full_mode and is_seen:
                    continue

                if slug not in self.discovered_slugs:
                    self.discovered_slugs.add(slug)
                    new_slugs_in_page += 1

                    if self.limit and len(self.discovered_slugs) >= self.limit:
                        self.stop_event.set()
                        break

            if not self.full_mode:
                if new_slugs_in_page == 0:
                    consecutive_empty_or_seen_pages += 1
                    if consecutive_empty_or_seen_pages >= self.state.incremental_stop:
                        break # Incremental mode stop logic triggered
                else:
                    consecutive_empty_or_seen_pages = 0

            progress.update(task_id, advance=1, description=f"Query '{query}' - Page {page} - New: {new_slugs_in_page}")
            page += 1

    async def run(self):
        with Progress() as progress:
            tasks = []
            for query in self.queries:
                task_id = progress.add_task(f"Query '{query}'", total=None)
                tasks.append(self._crawl_query(query, progress, task_id))

            await asyncio.gather(*tasks)

        await self.client.aclose()

        if not self.dry_run:
            self.state.merge(self.discovered_slugs)
            self.state.save()

        return list(self.discovered_slugs)
