import argparse
import asyncio
import json
from pathlib import Path
from rich.console import Console

from .state import StateManager
from .scraper import DiscoveryScraper

def main():
    parser = argparse.ArgumentParser(description="Ollama community model catalog scraper")
    subparsers = parser.add_subparsers(dest="command", required=True)

    discover_parser = subparsers.add_parser("discover", help="Discover models from Ollama")
    discover_parser.add_argument("--full", action="store_true", help="Ignore seen slugs, re-crawl everything")
    discover_parser.add_argument("--dry-run", action="store_true", help="Print slugs found, don't save")
    discover_parser.add_argument("--limit", type=int, help="Stop after N new slugs")

    args = parser.parse_args()

    if args.command == "discover":
        state = StateManager()
        scraper = DiscoveryScraper(state_manager=state, limit=args.limit, full_mode=args.full, dry_run=args.dry_run)

        console = Console()
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

if __name__ == "__main__":
    main()
