#!/usr/bin/env python3
"""
Explore the Ollama model catalog locally.

A fast, complete local alternative to ollama.com/models — all models, fresh data,
scoped search, size filtering, new-model highlighting, and tag alias detection.

Usage:
  python3 scripts/explore_catalog.py                         # top 20 by pulls
  python3 scripts/explore_catalog.py --stats                 # catalog summary
  python3 scripts/explore_catalog.py --search qwen           # search all fields
  python3 scripts/explore_catalog.py --search qwen --field name   # name only
  python3 scripts/explore_catalog.py --search embed --field desc  # desc only
  python3 scripts/explore_catalog.py --tag q4_K_M            # has a q4_K_M variant
  python3 scripts/explore_catalog.py --size 10:30            # variants 10–30 GB
  python3 scripts/explore_catalog.py --size :8               # variants up to 8 GB
  python3 scripts/explore_catalog.py --new 7                 # updated in last 7 days
  python3 scripts/explore_catalog.py --caps thinking,vision  # must have both caps
  python3 scripts/explore_catalog.py --type official         # official models only
  python3 scripts/explore_catalog.py --sort name             # sort alphabetically
  python3 scripts/explore_catalog.py --sort updated          # most recently updated first
  python3 scripts/explore_catalog.py --limit 0               # show all results
  python3 scripts/explore_catalog.py --show llama3.2         # full detail + alias map
  python3 scripts/explore_catalog.py HEAD~7                  # explore 7 commits ago
  python3 scripts/explore_catalog.py 2026-04-01              # explore at a date
"""
import argparse
import json
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Optional

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()

# ── data loading ──────────────────────────────────────────────────────────────

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


# ── time parsing ──────────────────────────────────────────────────────────────

_AGE_UNITS = {
    "second": 1 / 86400, "minute": 1 / 1440, "hour": 1 / 24,
    "day": 1, "week": 7, "month": 30, "year": 365,
}


def parse_age_days(updated: str) -> Optional[float]:
    """Parse '3 days ago', '2 weeks ago', etc. → approximate days. None if unknown."""
    if not updated:
        return None
    m = re.match(r"(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago",
                 updated.lower())
    if not m:
        return None
    return int(m.group(1)) * _AGE_UNITS.get(m.group(2), 0)


# ── filtering / sorting ───────────────────────────────────────────────────────

def _variant_sizes_gb(m):
    return [v["size_bytes"] / 1e9 for v in m.get("variants", []) if v.get("size_bytes", 0) > 0]


def apply_filters(models, search=None, field="all", caps=None, model_type=None,
                  tag_pattern=None, size_min=None, size_max=None, new_days=None):
    if search:
        q = search.lower()
        field_map = {
            "all":   lambda m: any([q in m.get("slug","").lower(),
                                    q in m.get("name","").lower(),
                                    q in m.get("blurb","").lower(),
                                    q in (m.get("description") or "").lower()]),
            "name":  lambda m: q in m.get("slug","").lower() or q in m.get("name","").lower(),
            "slug":  lambda m: q in m.get("slug","").lower(),
            "blurb": lambda m: q in m.get("blurb","").lower(),
            "desc":  lambda m: q in (m.get("description") or "").lower(),
        }
        fn = field_map.get(field, field_map["all"])
        models = [m for m in models if fn(m)]

    if caps:
        required = {c.strip().lower() for c in caps.split(",")}
        models = [m for m in models
                  if required.issubset({c.lower() for c in m.get("capabilities", [])})]

    if model_type:
        models = [m for m in models if m.get("model_type", "") == model_type]

    if tag_pattern:
        pat = tag_pattern.lower()
        models = [m for m in models
                  if any(pat in v.get("tag","").lower() for v in m.get("variants", []))]

    if size_min is not None or size_max is not None:
        lo = size_min or 0.0
        hi = size_max or float("inf")
        models = [m for m in models
                  if any(lo <= s <= hi for s in _variant_sizes_gb(m))]

    if new_days is not None:
        models = [m for m in models
                  if (age := parse_age_days(m.get("updated", ""))) is not None
                  and age <= new_days]

    return models


def apply_sort(models, sort_field):
    if sort_field == "pulls":
        return sorted(models, key=lambda m: m.get("pulls", 0), reverse=True)
    if sort_field == "name":
        return sorted(models, key=lambda m: m.get("slug", "").lower())
    if sort_field == "tags":
        return sorted(models, key=lambda m: m.get("tags_count", 0), reverse=True)
    if sort_field == "updated":
        # Sort by age ascending (most recent first); unknowns go last
        def age_key(m):
            a = parse_age_days(m.get("updated", ""))
            return a if a is not None else float("inf")
        return sorted(models, key=age_key)
    return models


# ── display helpers ───────────────────────────────────────────────────────────

CAP_COLORS = {"tools": "green", "vision": "blue", "thinking": "magenta", "embedding": "cyan"}


def fmt_caps(caps):
    parts = [f"[{CAP_COLORS.get(c, 'white')}]{c}[/{CAP_COLORS.get(c, 'white')}]"
             for c in sorted(caps)]
    return " ".join(parts) if parts else "[dim]-[/dim]"


def fmt_pulls(pulls_text):
    return pulls_text if pulls_text and pulls_text != "0" else "[dim]-[/dim]"


# ── views ─────────────────────────────────────────────────────────────────────

def show_list(models, limit, new_days=None):
    displayed = models[:limit] if limit > 0 else models

    table = Table(box=box.ROUNDED, highlight=True, show_footer=False, expand=True)
    table.add_column("#", justify="right", style="dim", no_wrap=True, min_width=3)
    table.add_column("Slug", style="cyan", ratio=3, no_wrap=True)
    table.add_column("Pulls", justify="right", style="yellow", no_wrap=True, min_width=6)
    table.add_column("Tags", justify="right", no_wrap=True, min_width=4)
    table.add_column("Capabilities", ratio=2, no_wrap=True)
    table.add_column("Blurb", ratio=4, no_wrap=True)

    for i, m in enumerate(displayed, 1):
        official = m.get("model_type") == "official"
        age = parse_age_days(m.get("updated", ""))
        is_new = new_days is not None and age is not None and age <= new_days
        new_badge = " [bold green]new[/bold green]" if is_new else ""
        slug = ("[bold]★ [/bold]" if official else "") + m["slug"] + new_badge
        blurb = (m.get("blurb") or "").strip().replace("\n", " ")
        table.add_row(
            str(i),
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

    # new-model breakdown
    new_7  = sum(1 for m in models if (a := parse_age_days(m.get("updated",""))) is not None and a <= 7)
    new_30 = sum(1 for m in models if (a := parse_age_days(m.get("updated",""))) is not None and a <= 30)

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
        f"[bold]Total pulls:[/bold] {total_pulls:,}  [dim](cumulative installs across all tags)[/dim]\n"
        f"[bold]Scraped:[/bold] {scraped_at}\n"
        f"[bold]Updated recently:[/bold] {new_7:,} in last 7d · {new_30:,} in last 30d\n\n"
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
        # Build alias map: group tags by size_bytes; identical size = likely same underlying layer
        size_to_tags: dict = defaultdict(list)
        for v in variants:
            sb = v.get("size_bytes", 0)
            if sb > 0:
                size_to_tags[sb].append(v.get("tag", ""))

        # For each size group with multiple tags, the FIRST tag is the "canonical" one
        # (ollama typically lists the specific quant before the alias)
        alias_of: dict = {}  # tag → canonical tag it aliases
        for sb, tags in size_to_tags.items():
            if len(tags) > 1:
                canonical = tags[0]
                for alias in tags[1:]:
                    alias_of[alias] = canonical

        vt = Table("Tag", "Size", "Context", "Input", "Note", box=box.SIMPLE_HEAD, expand=True)
        for v in variants:
            tag = v.get("tag", "")
            note = ""
            if tag in alias_of:
                # strip model prefix for brevity: "llama3.2:3b" → "3b"
                canon = alias_of[tag].split(":")[-1] if ":" in alias_of[tag] else alias_of[tag]
                note = f"[dim]≡ {canon}[/dim]"
            else:
                aliases_of_me = [t for t, c in alias_of.items() if c == tag]
                if aliases_of_me:
                    first = aliases_of_me[0].split(":")[-1]
                    rest = f" +{len(aliases_of_me)-1}" if len(aliases_of_me) > 1 else ""
                    note = f"[dim]← {first}{rest}[/dim]"
            vt.add_row(
                tag,
                v.get("size_text", "-"),
                v.get("context", "-"),
                v.get("input", "-"),
                note,
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

def parse_size_arg(s: str):
    """Parse 'MIN:MAX', ':MAX', 'MIN:' → (min_gb, max_gb). Either may be None."""
    parts = s.split(":")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("--size expects format MIN:MAX, e.g. 10:30 or :8")
    lo = float(parts[0]) if parts[0] else None
    hi = float(parts[1]) if parts[1] else None
    return lo, hi


def main():
    parser = argparse.ArgumentParser(
        description="Explore the Ollama model catalog",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__.split("Usage:")[1].strip() if "Usage:" in __doc__ else "",
    )
    parser.add_argument("ref", nargs="?", default=None,
                        help="Git ref or date (YYYY-MM-DD). Omit for current files.")
    parser.add_argument("--search", "-s", metavar="QUERY",
                        help="Search text (scope with --field)")
    parser.add_argument("--field", default="all",
                        choices=["all", "name", "slug", "blurb", "desc"],
                        help="Field to search (default: all)")
    parser.add_argument("--tag", metavar="PATTERN",
                        help="Filter to models with a variant tag containing PATTERN")
    parser.add_argument("--size", metavar="MIN:MAX",
                        help="Filter by variant size in GB (e.g. 10:30, :8, 20:)")
    parser.add_argument("--new", metavar="DAYS", type=int,
                        help="Filter/highlight models updated within N days")
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
                        help="Show full detail + alias map for a model")
    parser.add_argument("--stats", action="store_true",
                        help="Show catalog summary statistics")
    args = parser.parse_args()

    size_min = size_max = None
    if args.size:
        try:
            size_min, size_max = parse_size_arg(args.size)
        except argparse.ArgumentTypeError as e:
            parser.error(str(e))

    models, metadata = load_models(args.ref)

    if args.stats:
        show_stats(models, metadata)
        return

    if args.show:
        show_detail(models, args.show)
        return

    filtered = apply_filters(
        models,
        search=args.search,
        field=args.field,
        caps=args.caps,
        model_type=args.type,
        tag_pattern=args.tag,
        size_min=size_min,
        size_max=size_max,
        new_days=args.new,
    )
    sorted_models = apply_sort(filtered, args.sort)
    show_list(sorted_models, args.limit, new_days=args.new)


if __name__ == "__main__":
    main()
