#!/usr/bin/env python3
"""
Explore the Ollama model catalog locally.

A fast, complete local alternative to ollama.com/models — all models, fresh data,
filterable by capability, type, and full-text search.

Usage:
  python3 scripts/explore_catalog.py                       # top 20 by pulls
  python3 scripts/explore_catalog.py --stats               # catalog summary
  python3 scripts/explore_catalog.py --search qwen         # search name/slug/blurb
  python3 scripts/explore_catalog.py --caps tools          # must have 'tools'
  python3 scripts/explore_catalog.py --caps thinking,tools # must have both
  python3 scripts/explore_catalog.py --type official       # official models only
  python3 scripts/explore_catalog.py --sort name           # sort alphabetically
  python3 scripts/explore_catalog.py --limit 0             # show all results
  python3 scripts/explore_catalog.py --show llama3.2       # full detail for a model
  python3 scripts/explore_catalog.py HEAD~7                # explore 7 commits ago
  python3 scripts/explore_catalog.py 2026-04-01            # explore at a date
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# ── data loading (mirrors render_catalog.py) ─────────────────────────────────

def git_show(ref: str, path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        capture_output=True, text=True, check=True,
    )
    return result.stdout


def resolve_date(date_str: str) -> str:
    result = subprocess.run(
        ["git", "log", f"--before={date_str} 23:59:59", "-1", "--format=%H"],
        capture_output=True, text=True, check=True,
    )
    commit = result.stdout.strip()
    if not commit:
        raise SystemExit(f"error: no commits found on or before {date_str}")
    return commit


def load_models(ref=None):
    if ref is None:
        models: dict = {}
        with open("out/models.jsonl", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    m = json.loads(line)
                    models[m["slug"]] = m
        with open("out/pulls.jsonl", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    p = json.loads(line)
                    if p["slug"] in models:
                        models[p["slug"]]["pulls"] = p["pulls"]
                        models[p["slug"]]["pulls_text"] = p["pulls_text"]
        metadata = {}
        meta_path = Path("out/metadata.json")
        if meta_path.exists():
            with open(meta_path, encoding="utf-8") as f:
                metadata = json.load(f)
    else:
        if re.match(r"^\d{4}-\d{2}-\d{2}$", ref):
            ref = resolve_date(ref)
            console.print(f"[dim]Resolved to {ref[:12]}...[/dim]", file=sys.stderr)
        models: dict = {}
        for line in git_show(ref, "out/models.jsonl").splitlines():
            line = line.strip()
            if line:
                m = json.loads(line)
                models[m["slug"]] = m
        for line in git_show(ref, "out/pulls.jsonl").splitlines():
            line = line.strip()
            if line:
                p = json.loads(line)
                if p["slug"] in models:
                    models[p["slug"]]["pulls"] = p["pulls"]
                    models[p["slug"]]["pulls_text"] = p["pulls_text"]
        try:
            metadata = json.loads(git_show(ref, "out/metadata.json"))
        except subprocess.CalledProcessError:
            metadata = {}
    return list(models.values()), metadata


# ── filtering / sorting ───────────────────────────────────────────────────────

def apply_filters(models, search=None, caps=None, model_type=None):
    if search:
        q = search.lower()
        models = [
            m for m in models
            if q in m.get("slug", "").lower()
            or q in m.get("name", "").lower()
            or q in m.get("blurb", "").lower()
            or q in (m.get("description") or "").lower()
        ]
    if caps:
        required = {c.strip().lower() for c in caps.split(",")}
        models = [
            m for m in models
            if required.issubset({c.lower() for c in m.get("capabilities", [])})
        ]
    if model_type:
        models = [m for m in models if m.get("model_type", "") == model_type]
    return models


def apply_sort(models, sort_field):
    if sort_field == "pulls":
        return sorted(models, key=lambda m: m.get("pulls", 0), reverse=True)
    if sort_field == "name":
        return sorted(models, key=lambda m: m.get("slug", "").lower())
    if sort_field == "tags":
        return sorted(models, key=lambda m: m.get("tags_count", 0), reverse=True)
    if sort_field == "updated":
        return sorted(models, key=lambda m: m.get("updated", ""))
    return models


# ── display helpers ───────────────────────────────────────────────────────────

CAP_COLORS = {"tools": "green", "vision": "blue", "thinking": "magenta"}


def fmt_caps(caps):
    parts = [f"[{CAP_COLORS.get(c, 'white')}]{c}[/{CAP_COLORS.get(c, 'white')}]"
             for c in sorted(caps)]
    return " ".join(parts) if parts else "[dim]-[/dim]"


def fmt_pulls(pulls_text):
    return pulls_text if pulls_text and pulls_text != "0" else "[dim]-[/dim]"


# ── views ─────────────────────────────────────────────────────────────────────

def show_list(models, limit):
    displayed = models[:limit] if limit > 0 else models

    table = Table(box=box.ROUNDED, highlight=True, show_footer=False, expand=True)
    table.add_column("Slug", style="cyan", ratio=3, no_wrap=True)
    table.add_column("Pulls", justify="right", style="yellow", no_wrap=True, min_width=6)
    table.add_column("Tags", justify="right", no_wrap=True, min_width=4)
    table.add_column("Capabilities", ratio=2, no_wrap=True)
    table.add_column("Blurb", ratio=4, no_wrap=True)

    for m in displayed:
        official = m.get("model_type") == "official"
        slug = ("[bold]★ [/bold]" if official else "") + m["slug"]
        blurb = (m.get("blurb") or "").strip().replace("\n", " ")
        table.add_row(
            slug,
            fmt_pulls(m.get("pulls_text", "")),
            str(m.get("tags_count", "")),
            fmt_caps(m.get("capabilities", [])),
            blurb,
        )

    console.print(table)
    total = len(models)
    shown = len(displayed)
    suffix = f"  [dim]({total - shown} more — use --limit 0 to show all)[/dim]" if shown < total else ""
    console.print(f"[dim]{shown} model{'s' if shown != 1 else ''}[/dim]{suffix}")


def show_stats(models, metadata):
    total = len(models)
    official = sum(1 for m in models if m.get("model_type") == "official")
    community = total - official

    cap_counts: Counter = Counter()
    for m in models:
        for c in m.get("capabilities", []):
            cap_counts[c] += 1

    total_pulls = sum(m.get("pulls", 0) for m in models)
    top_ns = Counter(
        m.get("namespace", "") for m in models if m.get("model_type") == "community"
    )
    scraped_at = metadata.get("scraped_at", "unknown")

    cap_lines = "\n".join(
        f"  {fmt_caps([c])}  {n:,}" for c, n in sorted(cap_counts.items(), key=lambda x: -x[1])
    )
    ns_lines = "\n".join(
        f"  [cyan]{ns}[/cyan]  {n}" for ns, n in top_ns.most_common(10)
    )

    console.print(Panel(
        f"[bold]Models:[/bold] {total:,}  "
        f"([bold]official[/bold] {official} · [dim]community[/dim] {community})\n"
        f"[bold]Total pulls:[/bold] {total_pulls:,}\n"
        f"[bold]Scraped:[/bold] {scraped_at}\n\n"
        f"[bold]Capabilities:[/bold]\n{cap_lines}\n\n"
        f"[bold]Top community namespaces:[/bold]\n{ns_lines}",
        title="Catalog Stats",
        border_style="blue",
    ))


def show_detail(models, slug):
    matches = [m for m in models if m["slug"].lower() == slug.lower()]
    if not matches:
        matches = [m for m in models if slug.lower() in m["slug"].lower()]
    if not matches:
        console.print(f"[red]No model found matching '{slug}'[/red]")
        return
    if len(matches) > 1:
        console.print(f"[yellow]Multiple matches ({len(matches)}) — showing first. Use exact slug.[/yellow]")
    m = matches[0]

    mtype = "official" if m.get("model_type") == "official" else "community"
    header = (
        f"[bold cyan]{m['slug']}[/bold cyan]  [dim]{mtype}[/dim]\n"
        f"[yellow]{fmt_pulls(m.get('pulls_text', ''))} pulls[/yellow]  ·  "
        f"{m.get('tags_count', 0)} tags  ·  updated: {m.get('updated', '-')}\n"
        f"capabilities: {fmt_caps(m.get('capabilities', []))}\n\n"
        f"[italic]{(m.get('blurb') or '').strip()}[/italic]"
    )
    console.print(Panel(header, title="Model", border_style="cyan"))

    variants = m.get("variants", [])
    if variants:
        vt = Table("Tag", "Size", "Context", "Input", box=box.SIMPLE_HEAD)
        for v in variants:
            vt.add_row(
                v.get("tag", ""),
                v.get("size_text", "-"),
                v.get("context", "-"),
                v.get("input", "-"),
            )
        console.print(vt)

    desc = (m.get("description") or "").strip()
    if desc and desc != "No readme":
        lines = desc.splitlines()
        preview = "\n".join(lines[:40])
        if len(lines) > 40:
            preview += f"\n[dim]... ({len(lines) - 40} more lines)[/dim]"
        console.print(Panel(preview, title="README", border_style="dim"))


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Explore the Ollama model catalog",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Usage:")[1].strip() if "Usage:" in __doc__ else "",
    )
    parser.add_argument("ref", nargs="?", default=None,
                        help="Git ref or date (YYYY-MM-DD). Omit for current files.")
    parser.add_argument("--search", "-s", metavar="QUERY",
                        help="Search slug, name, blurb, description")
    parser.add_argument("--caps", "-c", metavar="CAP[,CAP]",
                        help="Filter by capability (comma-separated; model must have ALL listed)")
    parser.add_argument("--type", "-t", metavar="TYPE", choices=["official", "community"],
                        help="Filter by model type")
    parser.add_argument("--sort", default="pulls",
                        choices=["pulls", "name", "tags", "updated"],
                        help="Sort field (default: pulls)")
    parser.add_argument("--limit", "-n", type=int, default=20,
                        help="Max results (0 = all, default: 20)")
    parser.add_argument("--show", metavar="SLUG",
                        help="Show full detail for a model")
    parser.add_argument("--stats", action="store_true",
                        help="Show catalog summary statistics")
    args = parser.parse_args()

    models, metadata = load_models(args.ref)

    if args.stats:
        show_stats(models, metadata)
        return

    if args.show:
        show_detail(models, args.show)
        return

    filtered = apply_filters(models, search=args.search, caps=args.caps, model_type=args.type)
    sorted_models = apply_sort(filtered, args.sort)
    show_list(sorted_models, args.limit)


if __name__ == "__main__":
    main()
