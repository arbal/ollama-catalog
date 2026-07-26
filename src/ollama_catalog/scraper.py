import asyncio
import logging
import re
import string
from typing import Set, List, Optional
from html.parser import HTMLParser
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from rich.progress import Progress, TaskID

logger = logging.getLogger(__name__)

from .state import StateManager


class _SearchResultLinkParser(HTMLParser):
    """Extract model links from Ollama's search-result anchors only."""

    def __init__(self):
        super().__init__()
        self.slugs: List[str] = []

    def handle_starttag(self, tag: str, attrs):
        if tag != "a":
            return
        attributes = dict(attrs)
        classes = set(attributes.get("class", "").split())
        href = attributes.get("href", "")
        if {"group", "w-full"}.issubset(classes) and href.startswith("/"):
            slug = href[1:].split("?", 1)[0].split("#", 1)[0]
            if slug and "/" in slug:
                self.slugs.append(slug)

class DiscoveryScraper:
    def __init__(self, state_manager: StateManager, limit: Optional[int] = None, full_mode: bool = False, dry_run: bool = False):
        self.state = state_manager
        self.limit = limit
        self.full_mode = full_mode
        self.dry_run = dry_run

        # `observed_slugs` is the complete, de-duplicated result set seen during
        # this run. `discovered_slugs` remains the smaller fetch queue: only
        # slugs that were absent from the persisted seen-state when found.
        self.observed_slugs: Set[str] = set()
        self.discovered_slugs: Set[str] = set()
        # Keep listing requests bounded and paced for both modes. A full
        # reconciliation may make many requests, and a partial listing is
        # worse than a slower one because it could incorrectly prune records.
        self.semaphore = asyncio.Semaphore(5)
        self.client = httpx.AsyncClient(
            http2=True,
            follow_redirects=True,
            headers={
                "User-Agent": "Mozilla/5.0 (compatible; ollama-catalog/1.0)",
                # Search uses HTMX lazy pagination. Without this header Ollama
                # redirects every page after page one back to the first page.
                "HX-Request": "true",
            },
            timeout=30.0
        )
        # Empty query first: returns ~220 official/library models sorted by popularity.
        # Ensures official models aren't missed by the incremental stop in alphabet crawl.
        self.queries = [""] + list(string.ascii_lowercase + string.digits)
        self.stop_event = asyncio.Event()

    @retry(
        stop=stop_after_attempt(4),
        wait=wait_exponential(multiplier=0.5, min=0.5, max=6.0),
        retry=retry_if_exception_type((httpx.RequestError, httpx.HTTPStatusError))
    )
    async def _fetch_page(self, query: str, page: int) -> str:
        # Blank query: use default (popularity) sort to surface all official models.
        # Alphabet queries: use newest sort to surface recent community models.
        if query == "":
            url = f"https://ollama.com/search?page={page}"
        else:
            url = f"https://ollama.com/search?q={query}&o=newest&page={page}"
        async with self.semaphore:
            response = await self.client.get(url)
            response.raise_for_status()
            await asyncio.sleep(0.3)
            return response.text

    def _parse_slugs(self, html: str) -> List[str]:
        parser = _SearchResultLinkParser()
        parser.feed(html)
        return parser.slugs

    async def _crawl_query(self, query: str, progress: Progress, task_id: TaskID):
        page = 1
        consecutive_empty_or_seen_pages = 0

        while not self.stop_event.is_set():
            try:
                html = await self._fetch_page(query, page)
            except Exception as e:
                if self.full_mode:
                    raise RuntimeError(
                        f"Full coverage discovery failed for query {query!r} page {page}; "
                        "refusing to use a partial listing."
                    ) from e
                logger.warning(f"Error crawling query '{query}' page {page}: {e}")
                break

            slugs = self._parse_slugs(html)

            if not slugs:
                break # Empty page, done with this query

            new_slugs_in_page = 0
            for slug in slugs:
                if self.stop_event.is_set():
                    break

                self.observed_slugs.add(slug)
                is_seen = self.state.is_seen(slug)
                if is_seen:
                    continue

                if slug not in self.discovered_slugs:
                    self.discovered_slugs.add(slug)
                    new_slugs_in_page += 1

                    if self.limit and len(self.discovered_slugs) >= self.limit:
                        self.stop_event.set()
                        break

            # Blank query (official models): always paginate to exhaustion —
            # they're sorted by popularity, not newest, so old ones appear late.
            if not self.full_mode and query != "":
                if new_slugs_in_page == 0:
                    consecutive_empty_or_seen_pages += 1
                    if consecutive_empty_or_seen_pages >= self.state.incremental_stop:
                        break # Incremental mode stop logic triggered
                else:
                    consecutive_empty_or_seen_pages = 0

            progress.update(task_id, advance=1, description=f"Query '{query}' - Page {page} - New: {new_slugs_in_page}")
            page += 1

    async def run(self):
        try:
            with Progress() as progress:
                tasks = []
                for query in self.queries:
                    task_id = progress.add_task(f"Query '{query}'", total=None)
                    tasks.append(self._crawl_query(query, progress, task_id))

                await asyncio.gather(*tasks)
        finally:
            await self.client.aclose()

        if self.full_mode and not self.observed_slugs:
            raise RuntimeError(
                "Full coverage discovery extracted zero model links; "
                "refusing to use or replace discovery state."
            )

        if not self.dry_run:
            if self.full_mode:
                self.state.replace(self.observed_slugs)
            else:
                self.state.merge(self.discovered_slugs)
            self.state.save()

        return list(self.discovered_slugs)
