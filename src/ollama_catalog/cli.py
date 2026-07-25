import argparse
import asyncio
import json
import logging
from pathlib import Path
from rich.console import Console

from .state import StateManager
from .scraper import DiscoveryScraper
from .catalog import CatalogFetcher

def run_discover(args, console):
    state = StateManager()
    scraper = DiscoveryScraper(state_manager=state, limit=args.limit, full_mode=args.full, dry_run=args.dry_run)

    console.print("[bold green]Starting discovery...[/bold green]")

    discovered = asyncio.run(scraper.run())

    console.print(f"Found [bold blue]{len(discovered)}[/bold blue] new models.")

    if args.dry_run:
        console.print(discovered)
    else:
        out_file = Path("out/discovered_slugs.json")
        out_file.parent.mkdir(parents=True, exist_ok=True)
        with open(out_file, "w", encoding="utf-8") as f:
            json.dump(sorted(discovered), f, indent=2)
        console.print(f"Saved to [bold green]{out_file}[/bold green]")

def run_fetch(args, console):
    console.print("[bold green]Starting fetch...[/bold green]")
    delay_val = getattr(args, 'delay', 0.0)
    fetcher = CatalogFetcher(
        concurrency=args.concurrency if hasattr(args, 'concurrency') else 10,
        delay=delay_val
    )
    asyncio.run(fetcher.run(limit=args.limit, refetch=args.refetch))
    console.print(f"[bold green]Done fetching catalog![/bold green]")

def run_all(args, console):
    run_discover(args, console)
    if not getattr(args, 'dry_run', False):
        run_fetch(args, console)
    else:
        console.print("[bold yellow]Skipping fetch due to --dry-run[/bold yellow]")

def run_sanitize(args, console):
    fetcher = CatalogFetcher()
    result = fetcher.sanitize_committed_models()
    asyncio.run(fetcher.client.aclose())
    console.print(
        f"Sanitized [bold blue]{result.changed}[/bold blue] of "
        f"{result.records} model records."
    )

def main():
    parser = argparse.ArgumentParser(description="Ollama community model catalog scraper")
    parser.add_argument("--verbose", action="store_true", help="Enable verbose debug logging")

    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_parser = subparsers.add_parser("discover", help="Discover models from Ollama")
    discover_parser.add_argument("--full", action="store_true", help="Ignore seen slugs, re-crawl everything")
    discover_parser.add_argument("--dry-run", action="store_true", help="Print slugs found, don't save")
    discover_parser.add_argument("--limit", type=int, help="Stop after N new slugs")

    fetch_parser = subparsers.add_parser("fetch", help="Fetch model details")
    fetch_parser.add_argument("--refetch", action="store_true", help="Refetch all known models")
    fetch_parser.add_argument("--limit", type=int, help="Stop after fetching N models")
    fetch_parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent fetches")
    fetch_parser.add_argument("--delay", type=float, default=0.0, help="Optional delay in seconds between fetches (rate limiting)")

    run_parser = subparsers.add_parser("run", help="Discover then fetch details (normal daily workflow)")
    run_parser.add_argument("--full", action="store_true", help="Ignore seen slugs, re-crawl everything (discover)")
    run_parser.add_argument("--dry-run", action="store_true", help="Print slugs found, don't save (discover)")
    run_parser.add_argument("--refetch", action="store_true", help="Refetch all known models (fetch)")
    run_parser.add_argument("--limit", type=int, help="Stop after N items")
    run_parser.add_argument("--concurrency", type=int, default=10, help="Number of concurrent fetches (fetch)")
    run_parser.add_argument("--delay", type=float, default=0.0, help="Optional delay in seconds between fetches (rate limiting)")

    subparsers.add_parser("sanitize", help="Redact sensitive-looking text from committed models.jsonl without network access")

    args = parser.parse_args()
    console = Console()

    # Configure logging based on verbose flag
    if args.verbose:
        logging.basicConfig(
            level=logging.DEBUG,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
    else:
        logging.basicConfig(
            level=logging.WARNING,
            format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )

    if args.command == "discover":
        run_discover(args, console)
    elif args.command == "fetch":
        run_fetch(args, console)
    elif args.command == "run":
        run_all(args, console)
    elif args.command == "sanitize":
        run_sanitize(args, console)

if __name__ == "__main__":
    main()
