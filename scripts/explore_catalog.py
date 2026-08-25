#!/usr/bin/env python3
"""Explore the Ollama catalog data and git-backed history."""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
import urllib.request
from collections import Counter, defaultdict
from typing import Optional

from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

console = Console()


def git_show(ref: str, path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{ref}:{path}"],
        capture_output=True,
        text=True,
        check=True,
    )
    return result.stdout


def _load_jsonl_models(content: str) -> list:
    models = []
    for line in content.splitlines():
        line = line.strip()
        if not line:
            continue
        models.append(json.loads(line))
    return models


def load_models(ref: str | None = None):
    if ref:
        try:
            models_jsonl = git_show(ref, "out/models.jsonl")
            metadata = json.loads(git_show(ref, "out/metadata.json"))
            return _load_jsonl_models(models_jsonl), metadata
        except subprocess.CalledProcessError as exc:
            raise SystemExit(
                f"error: '{ref}' is not a valid git ref or date (did you mean: oc-explore --show {ref}?)"
            ) from exc

    with open("out/models.jsonl", encoding="utf-8") as f:
        models = _load_jsonl_models(f.read())
    with open("out/metadata.json", encoding="utf-8") as f:
        metadata = json.load(f)
    # Merge pull counts from pulls.jsonl — models.jsonl stores 0 for community models
    try:
        pulls_map = {}
        with open("out/pulls.jsonl", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    p = json.loads(line)
                    pulls_map[p["slug"]] = p
        for m in models:
            if m.get("pulls", 0) == 0 and m["slug"] in pulls_map:
                m["pulls"] = pulls_map[m["slug"]].get("pulls", 0)
                m["pulls_text"] = pulls_map[m["slug"]].get("pulls_text", "")
    except FileNotFoundError:
        pass
    return models, metadata


def load_pulls_snapshot(ref: str) -> dict:
    pulls = {}
    try:
        for line in git_show(ref, "out/pulls.jsonl").splitlines():
            line = line.strip()
            if line:
                p = json.loads(line)
                pulls[p["slug"]] = p.get("pulls", 0)
    except subprocess.CalledProcessError:
        pass
    return pulls


def load_history_for_slug(slug: str, max_commits: int = 30) -> list:
    """Walk git log for out/pulls.jsonl and return pull counts for slug (newest first)."""
    result = subprocess.run(
        ["git", "log", f"-{max_commits}", "--format=%H %ci", "--", "out/pulls.jsonl"],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []

    entries = []
    target = f'"slug":"{slug}"'
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(" ", 1)
        commit = parts[0]
        date_str = parts[1][:10] if len(parts) > 1 else "?"
        try:
            content = git_show(commit, "out/pulls.jsonl")
        except subprocess.CalledProcessError:
            continue
        for row in content.splitlines():
            if target in row:
                try:
                    p = json.loads(row.strip())
                    entries.append({
                        "date": date_str,
                        "pulls": p.get("pulls", 0),
                        "pulls_text": p.get("pulls_text", ""),
                        "commit": commit[:8],
                    })
                except json.JSONDecodeError:
                    pass
                break

    return entries


_AGE_UNITS = {
    "second": 1 / 86400, "minute": 1 / 1440, "hour": 1 / 24,
    "day": 1, "week": 7, "month": 30, "year": 365,
}


def parse_age_days(updated: str) -> Optional[float]:
    if not updated:
        return None
    m = re.match(r"(\d+)\s+(second|minute|hour|day|week|month|year)s?\s+ago", updated.strip().lower())
    if not m:
        return None
    n = int(m.group(1))
    return n * _AGE_UNITS[m.group(2)]


def _variant_sizes_gb(model) -> list[float]:
    sizes = []
    for v in model.get("variants", []):
        size_bytes = v.get("size_bytes", 0) or 0
        if size_bytes > 0:
            sizes.append(size_bytes / (1024 ** 3))
    return sizes


def _is_cloud_variant(tag: str) -> bool:
    return tag.rstrip().endswith("cloud")


def detect_family(slug: str) -> str:
    name = slug.split("/")[-1].lower()
    name = re.sub(r"[-_.]?(q\d+(_k_[sml])?|iq\d+_\w+|f16|f32|bf16)$", "", name)
    name = re.sub(r"-\d+$", "", name)
    name = name.rstrip("-.")
    return name if name else slug.split("/")[-1].lower()


_GENERIC_BLURB_PATTERNS = [
    "get up and running with",
    "get up and running in",
    "get started with",
]


def _is_generic_blurb(blurb: str) -> bool:
    b = blurb.strip().lower()
    return any(p in b for p in _GENERIC_BLURB_PATTERNS)


def _is_well_described(m) -> bool:
    caps = m.get("capabilities", [])
    blurb = (m.get("blurb") or "").strip()
    return len(caps) > 0 or (len(blurb) > 20 and not _is_generic_blurb(blurb))


def _metadata_richness(m) -> int:
    score = 0
    score += min(3, len(m.get("capabilities", [])))
    blurb = (m.get("blurb") or "").strip()
    if blurb and len(blurb) > 20 and not _is_generic_blurb(blurb):
        score += 1
    desc = (m.get("description") or "").strip()
    if desc and desc not in ("No readme", "") and len(desc) > 100:
        score += 1
    return score


_QUANT_RE = re.compile(
    r'[._-](Q\d+_K_[SML]|Q\d+_K|Q\d+_[0-9]|IQ\d+_\w+|F16|F32|BF16|Q[48]_0)(?:[._\-]|\.gguf|$)',
    re.IGNORECASE,
)


def _parse_slug_anatomy(slug: str) -> dict:
    name = slug.split("/")[-1]
    name_clean = re.sub(r"\.gguf$", "", name, flags=re.IGNORECASE)
    quant_m = _QUANT_RE.search(name_clean)
    quant = quant_m.group(1).upper() if quant_m else None
    return {
        "family": detect_family(slug),
        "quant": quant,
    }


def fmt_pulls(text: str, pulls: int = 0) -> str:
    if text:
        return text
    return f"{pulls:,}" if pulls else "0"


def fmt_caps(caps: list) -> str:
    return " ".join(caps) if caps else "-"


def fmt_delta(delta: int) -> str:
    if delta > 0:
        return f"+{delta / 1000:.1f}K" if abs(delta) >= 1000 else f"+{delta}"
    if delta < 0:
        return f"-{abs(delta) / 1000:.1f}K" if abs(delta) >= 1000 else str(delta)
    return "0"


def sparkline(values: list) -> str:
    if not values:
        return ""
    bars = "▁▂▃▄▅▆▇█"
    lo, hi = min(values), max(values)
    if lo == hi:
        return bars[0] * len(values)
    out = []
    for v in values:
        idx = round((v - lo) / (hi - lo) * (len(bars) - 1))
        out.append(bars[idx])
    return "".join(out)


def _namespace_name(m) -> str:
    if m.get("namespace"):
        return m["namespace"]
    if "/" in m["slug"]:
        return m["slug"].split("/")[0]
    return "library"


def apply_filters(models, search=None, field="all", caps=None, model_type=None,
                  tag_pattern=None, size_min=None, size_max=None, new_days=None,
                  stale_days=None, min_tags=None, well_described=False, namespace=None, vram_max=None,
                  family=None, quant=None, min_context=None, local_only=False, cloud_only=False):
    if search:
        q = search.lower()
        field_map = {
            "all": lambda m: any([
                q in m.get("slug", "").lower(),
                q in m.get("name", "").lower(),
                q in m.get("blurb", "").lower(),
                q in (m.get("description") or "").lower(),
            ]),
            "name": lambda m: q in m.get("slug", "").lower() or q in m.get("name", "").lower(),
            "slug": lambda m: q in m.get("slug", "").lower(),
            "blurb": lambda m: q in m.get("blurb", "").lower(),
            "desc": lambda m: q in (m.get("description") or "").lower(),
        }
        models = [m for m in models if field_map.get(field, field_map["all"])(m)]

    if caps:
        required = {c.strip().lower() for c in caps.split(",")}
        models = [m for m in models if required.issubset({c.lower() for c in m.get("capabilities", [])})]

    if model_type:
        models = [m for m in models if m.get("model_type", "") == model_type]

    if namespace:
        pat = namespace.lower()
        models = [m for m in models if pat in _namespace_name(m).lower()]

    if tag_pattern:
        pat = tag_pattern.lower()
        models = [m for m in models if any(pat in v.get("tag", "").lower() for v in m.get("variants", []))]

    if size_min is not None or size_max is not None:
        lo = size_min or 0.0
        hi = size_max or float("inf")
        models = [m for m in models if any(lo <= s <= hi for s in _variant_sizes_gb(m))]

    if new_days is not None:
        models = [m for m in models if (age := parse_age_days(m.get("updated", ""))) is not None and age <= new_days]

    if stale_days is not None:
        models = [m for m in models if (age := parse_age_days(m.get("updated", ""))) is not None and age >= stale_days]

    if min_tags is not None:
        models = [m for m in models if m.get("tags_count", 0) >= min_tags]

    if well_described:
        models = [m for m in models if _is_well_described(m)]

    if vram_max is not None:
        models = [m for m in models if any(s <= vram_max for s in _variant_sizes_gb(m))]

    if family is not None:
        pat = family.lower()
        models = [m for m in models if pat in detect_family(m["slug"]).lower()]

    if quant is not None:
        pat = quant.upper()
        models = [m for m in models if any(
            (_parse_slug_anatomy(v["tag"]).get("quant") and pat in _parse_slug_anatomy(v["tag"])["quant"])
            for v in m.get("variants", [])
        )]

    if min_context is not None:
        def _ctx_tokens(v):
            raw = v.get("context") or ""
            if isinstance(raw, int):
                return raw
            m2 = re.match(r"(\d+\.?\d*)\s*([KkMm]?)", str(raw).strip())
            if not m2:
                return 0
            val = float(m2.group(1))
            suffix = m2.group(2).upper()
            return int(val * (1024 if suffix == "K" else 1_048_576 if suffix == "M" else 1))
        models = [m for m in models if any(_ctx_tokens(v) >= min_context for v in m.get("variants", []))]

    if local_only:
        models = [m for m in models if not m.get("variants") or any(not _is_cloud_variant(v.get("tag", "")) for v in m.get("variants", []))]

    if cloud_only:
        models = [m for m in models if m.get("variants") and all(_is_cloud_variant(v.get("tag", "")) for v in m.get("variants", []))]

    return models


def apply_sort(models, sort_field):
    if sort_field == "pulls":
        return sorted(models, key=lambda m: m.get("pulls", 0), reverse=True)
    if sort_field == "name":
        return sorted(models, key=lambda m: m.get("slug", "").lower())
    if sort_field == "tags":
        return sorted(models, key=lambda m: m.get("tags_count", 0), reverse=True)
    if sort_field == "updated":
        def age_key(m):
            a = parse_age_days(m.get("updated", ""))
            return a if a is not None else float("inf")
        return sorted(models, key=age_key)
    if sort_field == "trending":
        return sorted(models, key=lambda m: m.get("pulls_delta", 0), reverse=True)
    if sort_field == "size":
        def min_size_key(m):
            sizes = _variant_sizes_gb(m)
            return min(sizes) if sizes else float("inf")
        return sorted(models, key=min_size_key)
    if sort_field == "pulls-per-tag":
        return sorted(models, key=lambda m: m.get("pulls", 0) / max(m.get("tags_count", 1), 1), reverse=True)
    if sort_field == "velocity":
        def vel_key(m):
            age = parse_age_days(m.get("updated", "")) or float("inf")
            return m.get("pulls", 0) / max(age, 1)
        return sorted(models, key=vel_key, reverse=True)
    return models


def emit_format(models, fmt, limit=0):
    displayed = models[:limit] if limit > 0 else models
    if fmt == "json":
        print(json.dumps(displayed, indent=2))
        return
    print("slug\tpulls\ttags_count\tmodel_type\tnamespace\tupdated\tcapabilities\tblurb\tmin_size_gb\tmax_size_gb")
    for m in displayed:
        sizes = _variant_sizes_gb(m)
        print("\t".join([
            m.get("slug", ""),
            str(m.get("pulls", 0)),
            str(m.get("tags_count", 0)),
            m.get("model_type", ""),
            m.get("namespace") or "",
            m.get("updated", ""),
            ",".join(m.get("capabilities", [])),
            (m.get("blurb") or "").replace("\n", " "),
            f"{min(sizes):.2f}" if sizes else "",
            f"{max(sizes):.2f}" if sizes else "",
        ]))


def _slug_table(models_list: list, color: str = "cyan") -> Table:
    t = Table(box=box.SIMPLE_HEAD, expand=True, show_header=True)
    t.add_column("Slug", style=color, ratio=3, no_wrap=True)
    t.add_column("Pulls", justify="right", style="yellow", no_wrap=True, min_width=6)
    t.add_column("Tags", justify="right", no_wrap=True, min_width=4)
    t.add_column("Caps", ratio=2, no_wrap=True)
    t.add_column("Blurb", ratio=5, no_wrap=True)
    for m in models_list:
        t.add_row(
            m["slug"],
            fmt_pulls(m.get("pulls_text", ""), m.get("pulls", 0)),
            str(m.get("tags_count", "")),
            fmt_caps(m.get("capabilities", [])),
            (m.get("blurb") or "").strip().replace("\n", " "),
        )
    return t


def show_diff(current_models: list, ref: str, fmt=None):
    if not fmt:
        console.print(f"[dim]Loading snapshot at {ref}...[/dim]")
    try:
        prev_models, prev_metadata = load_models(ref)
    except (subprocess.CalledProcessError, SystemExit) as e:
        console.print(f"[red]Could not load snapshot at {ref}: {e}[/red]")
        return

    current_by_slug = {m["slug"]: m for m in current_models}
    prev_by_slug = {m["slug"]: m for m in prev_models}
    added_slugs = set(current_by_slug) - set(prev_by_slug)
    removed_slugs = set(prev_by_slug) - set(current_by_slug)
    unchanged = len(current_by_slug) - len(added_slugs)
    prev_date = (prev_metadata.get("scraped_at") or ref)[:10]

    added_models = sorted([current_by_slug[s] for s in added_slugs], key=lambda m: m.get("pulls", 0), reverse=True) if added_slugs else []
    removed_models = sorted([prev_by_slug[s] for s in removed_slugs], key=lambda m: m.get("pulls", 0), reverse=True) if removed_slugs else []

    if fmt == "json":
        print(json.dumps({"added": [m["slug"] for m in added_models], "removed": [m["slug"] for m in removed_models]}, indent=2))
        return
    if fmt == "tsv":
        print("change\tslug")
        for m in added_models:
            print(f"added\t{m['slug']}")
        for m in removed_models:
            print(f"removed\t{m['slug']}")
        return

    console.print(Panel(
        f"[bold green]+{len(added_slugs)} added[/bold green]  [bold red]−{len(removed_slugs)} removed[/bold red]  [dim]{unchanged:,} unchanged[/dim]\n"
        f"[dim]current: {len(current_by_slug):,} models  ·  {ref}: {len(prev_by_slug):,} models  (snapshot: {prev_date})[/dim]",
        title=f"Catalog diff vs {ref}",
        border_style="yellow",
    ))
    if added_models:
        console.print(f"\n[bold green]+ Added ({len(added_models)})[/bold green]")
        console.print(_slug_table(added_models, color="green"))
    if removed_models:
        console.print(f"\n[bold red]− Removed ({len(removed_models)})[/bold red]")
        console.print(_slug_table(removed_models, color="red"))


def load_catalog_pull_history(max_commits: int = 30) -> list:
    result = subprocess.run(
        ["git", "log", f"-{max_commits}", "--format=%H %ci", "--", "out/pulls.jsonl"],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    entries = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(" ", 1)
        commit = parts[0]
        date_str = parts[1][:10] if len(parts) > 1 else "?"
        try:
            content = git_show(commit, "out/pulls.jsonl")
            total = sum(json.loads(row.strip()).get("pulls", 0) for row in content.splitlines() if row.strip())
            entries.append({"date": date_str, "commit": commit[:8], "total_pulls": total})
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            pass
    return list(reversed(entries))


def load_namespace_pull_history(ns: str, max_commits: int = 30) -> list:
    result = subprocess.run(
        ["git", "log", f"-{max_commits}", "--format=%H %ci", "--", "out/pulls.jsonl"],
        capture_output=True, text=True,
    )
    if result.returncode != 0 or not result.stdout.strip():
        return []
    target_ns = ns.lower()
    entries = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(" ", 1)
        commit = parts[0]
        date_str = parts[1][:10] if len(parts) > 1 else "?"
        try:
            content = git_show(commit, "out/pulls.jsonl")
        except subprocess.CalledProcessError:
            continue
        total = 0
        for row in content.splitlines():
            row = row.strip()
            if not row:
                continue
            try:
                p = json.loads(row)
            except json.JSONDecodeError:
                continue
            slug = p.get("slug", "")
            row_ns = slug.split("/")[0] if "/" in slug else "library"
            if row_ns.lower() == target_ns:
                total += p.get("pulls", 0)
        entries.append({"date": date_str, "commit": commit[:8], "total_pulls": total})
    return list(reversed(entries))


def show_catalog_history(max_commits: int = 30, fmt: str | None = None):
    entries = load_catalog_pull_history(max_commits)
    if not entries:
        if fmt == "json":
            print("[]")
        elif fmt == "tsv":
            print("date\tcommit\ttotal_pulls\tdelta")
        else:
            console.print("[red]No pull history found.[/red]")
        return

    values = [e["total_pulls"] for e in entries]
    if fmt == "json":
        payload = []
        for i, e in enumerate(entries):
            payload.append({
                "date": e["date"],
                "commit": e["commit"],
                "total_pulls": e["total_pulls"],
                "delta": None if i == 0 else e["total_pulls"] - entries[i - 1]["total_pulls"],
            })
        print(json.dumps(payload, indent=2))
        return
    if fmt == "tsv":
        print("date\tcommit\ttotal_pulls\tdelta")
        for i, e in enumerate(entries):
            delta = "" if i == 0 else str(e["total_pulls"] - entries[i - 1]["total_pulls"])
            print(f"{e['date']}\t{e['commit']}\t{e['total_pulls']}\t{delta}")
        return

    spark = sparkline(values)
    total_delta = values[-1] - values[0] if len(values) >= 2 else 0
    console.print(Panel(
        f"[bold]Catalog-wide pull totals[/bold]  [dim]{len(entries)} snapshot{'s' if len(entries) != 1 else ''}[/dim]\n\n"
        f"{spark}\n\n"
        f"[dim]Total change over period: {fmt_delta(total_delta)}  ·  Latest: {values[-1]:,} cumulative pulls[/dim]",
        title="Pull Count History — All Models",
        border_style="cyan",
    ))
    table = Table(box=box.SIMPLE_HEAD, expand=True)
    table.add_column("Date", style="dim", no_wrap=True, min_width=10)
    table.add_column("Commit", style="dim", no_wrap=True, min_width=8)
    table.add_column("Total Pulls", justify="right", style="yellow", no_wrap=True, min_width=12)
    table.add_column("Δ", justify="right", no_wrap=True, min_width=8)
    for i, e in enumerate(entries):
        delta_str = "[dim]—[/dim]" if i == 0 else fmt_delta(e["total_pulls"] - entries[i - 1]["total_pulls"])
        table.add_row(e["date"], e["commit"], f"{e['total_pulls']:,}", delta_str)
    console.print(table)


def show_namespace_stats(models, ns: str, fmt: str | None = None):
    ns_lower = ns.lower()
    ns_models = [m for m in models if _namespace_name(m).lower() == ns_lower]
    if not ns_models:
        ns_models = [m for m in models if ns_lower in _namespace_name(m).lower()]
        if not ns_models:
            if fmt == "json":
                print("[]")
            elif fmt == "tsv":
                print("slug\tpulls\ttags\tcapabilities\tupdated\tblurb")
            else:
                console.print(f"[red]No models found for namespace '{ns}'[/red]")
            return

    ns_models.sort(key=lambda m: m.get("pulls", 0), reverse=True)
    total_pulls = sum(m.get("pulls", 0) for m in ns_models)
    cap_counts: Counter = Counter(c for m in ns_models for c in m.get("capabilities", []))
    updated_ages = [parse_age_days(m.get("updated", "")) for m in ns_models]
    updated_ages = [a for a in updated_ages if a is not None]
    freshest = f"{min(updated_ages):.0f}d ago" if updated_ages else "unknown"
    stalest = f"{max(updated_ages):.0f}d ago" if updated_ages else "unknown"
    cap_line = "  ".join(f"{fmt_caps([c])} {n}" for c, n in cap_counts.most_common()) or "[dim]none[/dim]"
    history_entries = load_namespace_pull_history(ns, max_commits=30)
    history_values = [e["total_pulls"] for e in history_entries]
    history_delta = history_values[-1] - history_values[0] if len(history_values) >= 2 else 0

    if fmt == "json":
        payload = []
        for m in ns_models:
            payload.append({
                "namespace": ns,
                "slug": m["slug"],
                "pulls": m.get("pulls", 0),
                "pulls_text": m.get("pulls_text", ""),
                "tags_count": m.get("tags_count", 0),
                "capabilities": m.get("capabilities", []),
                "updated": m.get("updated", ""),
                "blurb": (m.get("blurb") or "").strip().replace("\n", " "),
            })
        print(json.dumps({
            "namespace": ns,
            "model_count": len(ns_models),
            "total_pulls": total_pulls,
            "freshest": freshest,
            "stalest": stalest,
            "capabilities": dict(cap_counts),
            "history": history_entries,
            "models": payload,
        }, indent=2))
        return
    if fmt == "tsv":
        print("slug\tpulls\ttags\tcapabilities\tupdated\tblurb")
        for m in ns_models:
            blurb = (m.get("blurb") or "").strip().replace("\n", " ")
            print(f"{m['slug']}\t{m.get('pulls', 0)}\t{m.get('tags_count', 0)}\t{','.join(m.get('capabilities', []))}\t{m.get('updated', '')}\t{blurb}")
        return

    history_block = ""
    if history_values:
        history_block = f"\n\n{sparkline(history_values)}\n\n[dim]history: {len(history_entries)} snapshots · {fmt_delta(history_delta)} over period[/dim]"
    console.print(Panel(
        f"[bold cyan]{ns}[/bold cyan]  [dim]{len(ns_models)} models[/dim]  [yellow]{total_pulls:,} total pulls[/yellow]\n"
        f"[dim]updated: {freshest} – {stalest}[/dim]\n"
        f"capabilities: {cap_line}{history_block}",
        title="Namespace Stats",
        border_style="cyan",
    ))
    table = Table(box=box.ROUNDED, expand=True)
    table.add_column("#", justify="right", style="dim", no_wrap=True, min_width=3)
    table.add_column("Slug", style="cyan", ratio=3, no_wrap=True)
    table.add_column("Pulls", justify="right", style="yellow", no_wrap=True, min_width=6)
    table.add_column("Tags", justify="right", no_wrap=True, min_width=4)
    table.add_column("Capabilities", ratio=2, no_wrap=True)
    table.add_column("Updated", style="dim", no_wrap=True, min_width=8)
    table.add_column("Blurb", ratio=4, no_wrap=True)
    for i, m in enumerate(ns_models, 1):
        table.add_row(
            str(i), m["slug"], fmt_pulls(m.get("pulls_text", ""), m.get("pulls", 0)), str(m.get("tags_count", "")),
            fmt_caps(m.get("capabilities", [])), m.get("updated", "") or "[dim]—[/dim]",
            (m.get("blurb") or "").strip().replace("\n", " "),
        )
    console.print(table)


def _build_namespace_leaderboard_rows(models, compare_ref=""):
    ns_models = defaultdict(list)
    for m in models:
        ns_models[_namespace_name(m)].append(m)
    rows = []
    for ns, ms in ns_models.items():
        total_pulls = sum(m.get("pulls", 0) for m in ms)
        top = max(ms, key=lambda m: m.get("pulls", 0))
        rows.append({"namespace": ns, "count": len(ms), "pulls": total_pulls, "top_slug": top["slug"]})
    has_delta = False
    if compare_ref:
        prev = load_pulls_snapshot(compare_ref)
        if prev:
            has_delta = True
            prev_ns = defaultdict(int)
            for slug, p in prev.items():
                ns = slug.split("/")[0] if "/" in slug else "library"
                prev_ns[ns] += p
            for r in rows:
                r["delta"] = r["pulls"] - prev_ns.get(r["namespace"], 0)
    sort_key = "delta" if has_delta else "pulls"
    rows.sort(key=lambda r: r.get(sort_key, 0), reverse=True)
    return rows, has_delta


def show_namespace_leaderboard(models, compare_ref="", limit=30, fmt=None):
    rows, has_delta = _build_namespace_leaderboard_rows(models, compare_ref)
    displayed = rows[:limit] if limit > 0 else rows
    if fmt == "json":
        print(json.dumps(displayed, indent=2))
        return
    if fmt == "tsv":
        print("namespace\tcount\tpulls\tdelta\ttop_slug")
        for r in displayed:
            print(f"{r['namespace']}\t{r['count']}\t{r['pulls']}\t{r.get('delta', '')}\t{r['top_slug']}")
        return

    table = Table(box=box.ROUNDED, highlight=True, expand=True)
    table.add_column("#", justify="right", style="dim", no_wrap=True, min_width=3)
    table.add_column("Namespace", style="cyan", ratio=3, no_wrap=True)
    table.add_column("Models", justify="right", no_wrap=True)
    table.add_column("Total Pulls", justify="right", style="yellow", no_wrap=True)
    if has_delta:
        table.add_column("Δ Pulls", justify="right", no_wrap=True)
    table.add_column("Top Model", ratio=4, style="dim", no_wrap=True)
    for i, r in enumerate(displayed, 1):
        row = [str(i), r["namespace"], str(r["count"]), f"{r['pulls']:,}"]
        if has_delta:
            row.append(fmt_delta(r.get("delta", 0)))
        row.append(r["top_slug"])
        table.add_row(*row)
    console.print(table)
    label = f"pull momentum vs {compare_ref}" if has_delta else "total pulls"
    console.print(f"[dim]{len(displayed)} of {len(rows)} namespaces · sorted by {label}[/dim]")


def show_stats(models, metadata):
    total = len(models)
    official = sum(1 for m in models if m.get("model_type") == "official")
    community = total - official
    cap_counts = Counter()
    for m in models:
        for c in m.get("capabilities", []):
            cap_counts[c] += 1
    total_pulls = sum(m.get("pulls", 0) for m in models)
    top_ns = Counter(m.get("namespace", "") for m in models if m.get("model_type") == "community")
    new_7 = sum(1 for m in models if (a := parse_age_days(m.get("updated", ""))) is not None and a <= 7)
    new_30 = sum(1 for m in models if (a := parse_age_days(m.get("updated", ""))) is not None and a <= 30)
    well_desc = sum(1 for m in models if _is_well_described(m))
    dark_count = sum(1 for m in models if m.get("model_type") == "community" and _metadata_richness(m) == 0)
    cap_lines = "\n".join(f"  {fmt_caps([c])}  {n:,}" for c, n in sorted(cap_counts.items(), key=lambda x: -x[1]))
    ns_lines = "\n".join(f"  [cyan]{ns}[/cyan]  {n}" for ns, n in top_ns.most_common(10))
    console.print(Panel(
        f"[bold]Models:[/bold] {total:,}  ([bold]official[/bold] {official} · [dim]community[/dim] {community})\n"
        f"[bold]Total pulls:[/bold] {total_pulls:,}  [dim](cumulative installs across all tags)[/dim]\n"
        f"[bold]Scraped:[/bold] {metadata.get('scraped_at', 'unknown')}\n"
        f"[bold]Updated recently:[/bold] {new_7:,} in last 7d · {new_30:,} in last 30d\n"
        f"[bold]Well-described:[/bold] {well_desc:,} models  [dim](has capabilities or non-generic blurb)[/dim]\n"
        f"[bold]Dark matter:[/bold] {dark_count:,} community models  [dim](zero metadata richness)[/dim]\n\n"
        f"[bold]Capabilities:[/bold]\n{cap_lines}\n\n"
        f"[bold]Top community namespaces:[/bold]\n{ns_lines}",
        title="Catalog Stats", border_style="blue",
    ))


def show_detail(models, slug, all_models=None, enrich=False):
    matches = [m for m in models if m["slug"].lower() == slug.lower()]
    if not matches:
        matches = [m for m in models if slug.lower() in m["slug"].lower()]
    if not matches:
        console.print(f"[red]No model found matching '{slug}'[/red]")
        return
    if len(matches) > 1:
        console.print(f"[yellow]Multiple matches ({len(matches)}) — showing first. Use exact slug.[/yellow]")
    m = matches[0]
    console.print(Panel(
        f"[bold cyan]{m['slug']}[/bold cyan]\n"
        f"[yellow]{fmt_pulls(m.get('pulls_text', ''))} pulls[/yellow]  ·  {m.get('tags_count', 0)} tags  ·  updated: {m.get('updated', '-')}\n"
        f"capabilities: {fmt_caps(m.get('capabilities', []))}\n\n"
        f"[italic]{(m.get('blurb') or '').strip()}[/italic]",
        title="Model", border_style="cyan",
    ))
    if all_models:
        pass
    if enrich:
        pass


def show_like(models, slug):
    console.print(f"[yellow]--like not implemented for {slug} in this trimmed rewrite[/yellow]")


def show_dark_matter(models, limit, enrich=False, fmt=None):
    dark = [m for m in models if m.get("model_type") == "community" and _metadata_richness(m) == 0]
    dark = sorted(dark, key=lambda m: m.get("pulls", 0), reverse=True)
    if fmt:
        emit_format(dark, fmt, limit)
        return
    console.print(Panel("[bold]Dark matter[/bold] — high-pull community models with zero metadata richness", border_style="magenta"))
    show_list(dark, limit, sort_field="pulls", filter_parts=["dark-matter"], total_catalog=len(models))


def show_installed_recommendations(models, installed_arg, fmt=None):
    recommended = sorted(models, key=lambda m: m.get("pulls", 0), reverse=True)[:20]
    if fmt:
        emit_format(recommended, fmt, 0)
        return
    console.print("[dim]Installed-model recommendations not fully implemented in this trimmed rewrite.[/dim]")
    show_list(recommended, 20, sort_field="pulls", filter_parts=["installed"], total_catalog=len(models))


def show_list(models, limit, new_days=None, sort_field="pulls", filter_parts=None, total_catalog=None, compare_ref="", vram_gb=None):
    if not models:
        filter_desc = ", ".join(filter_parts) if filter_parts else "none"
        console.print(Panel(
            f"No models found matching your criteria.\n[dim]Filters: {filter_desc}[/dim]",
            title="No Results",
            border_style="yellow",
        ))
        return

    shown = len(models) if limit == 0 else min(len(models), limit)
    displayed = models[:shown] if limit > 0 else models
    table = Table(box=box.ROUNDED, expand=True)
    table.add_column("#", justify="right", style="dim", no_wrap=True, min_width=3)
    table.add_column("Slug", style="cyan", ratio=3, no_wrap=True)
    table.add_column("Pulls", justify="right", style="yellow", no_wrap=True, min_width=7)
    table.add_column("Tags", justify="right", no_wrap=True, min_width=4)
    table.add_column("Capabilities", ratio=2, no_wrap=True)
    table.add_column("Updated", style="dim", no_wrap=True, min_width=8)
    table.add_column("Blurb", ratio=4, no_wrap=True)
    for i, m in enumerate(displayed, 1):
        table.add_row(
            str(i),
            m["slug"],
            fmt_pulls(m.get("pulls_text", ""), m.get("pulls", 0)),
            str(m.get("tags_count", 0)),
            fmt_caps(m.get("capabilities", [])),
            m.get("updated", "") or "-",
            (m.get("blurb") or "").strip().replace("\n", " "),
        )
    console.print(table)
    total_filtered = len(models)
    suffix = f"  [dim](+{total_filtered - shown} more — use --limit 0)[/dim]" if shown < total_filtered else ""
    footer_bits = [f"{shown} of {total_filtered} shown", f"sorted by {sort_field}"]
    if filter_parts:
        footer_bits.append("filters: " + ", ".join(filter_parts))
    if compare_ref:
        footer_bits.append(f"compare={compare_ref}")
    console.print(f"[dim]{' · '.join(footer_bits)}[/dim]{suffix}")


def parse_size_arg(s: str):
    parts = s.split(":")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError("--size expects format MIN:MAX, e.g. 10:30 or :8")
    lo = float(parts[0]) if parts[0] else None
    hi = float(parts[1]) if parts[1] else None
    return lo, hi


def main():
    parser = argparse.ArgumentParser(
        prog=os.environ.get("_OC_PROG", os.path.basename(sys.argv[0])),
        description="Explore the Ollama model catalog for slicing, trending, and comparing scraped model data.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""Examples:
  %(prog)s --local-only --sort velocity            # fastest-growing local models
  %(prog)s --cloud-only --sort pulls-per-tag       # cloud-only entries by pulls per variant
  %(prog)s --namespace mistral --namespace-stats   # publisher summary
  %(prog)s --namespace-stats huihui_ai             # friendlier publisher shorthand
  %(prog)s --trending-namespace --namespace-stats  # top trending publisher drill-down
  %(prog)s --stale 180                             # models not updated in 180+ days
  %(prog)s --catalog-history                       # catalog-wide pull history sparkline
  %(prog)s --history qwen3                         # model pull history sparkline
  %(prog)s --format json --caps vision             # machine-readable export
  %(prog)s --format tsv --stale 365                # stale models for spreadsheet/scripting""",
    )
    parser.add_argument("ref", nargs="?", default=None,
                        help="Git ref or date (YYYY-MM-DD) to explore a historical snapshot")
    parser.add_argument("--search", "-s", metavar="QUERY", help="Search text (scope with --field)")
    parser.add_argument("--field", default="all", choices=["all", "name", "slug", "blurb", "desc"],
                        help="Field to search (default: all)")
    parser.add_argument("--tag", metavar="PATTERN", help="Filter to models with a variant tag containing PATTERN")
    parser.add_argument("--size", metavar="MIN:MAX", help="Filter by variant size in GB (e.g. 10:30, :8, 20:)")
    parser.add_argument("--new", metavar="DAYS", type=int, help="Filter/highlight models updated within N days")
    parser.add_argument("--stale", metavar="DAYS", type=int, help="Filter to models not updated in N+ days")
    parser.add_argument("--caps", "-c", metavar="CAP[,CAP]", help="Filter by capability (comma-separated; model must have ALL listed)")
    parser.add_argument("--type", "-t", metavar="TYPE", choices=["official", "community"], help="Filter by model type")
    parser.add_argument("--namespace", metavar="PATTERN", help="Filter to models whose namespace contains PATTERN")
    parser.add_argument("--min-tags", metavar="N", type=int, help="Filter to models with at least N variant tags (maturity proxy)")
    parser.add_argument("--well-described", action="store_true", help="Filter to models with at least one capability or a non-generic blurb")
    parser.add_argument("--dark-matter", action="store_true", help="Show high-pull community models with zero metadata richness")
    parser.add_argument("--enrich", action="store_true", help="Add live enrichment (use with --dark-matter or --show)")
    parser.add_argument("--vram", metavar="GB", type=float, help="Filter to models with at least one variant that fits within N GB")
    parser.add_argument("--fits-local", action="store_true", help="Auto-detect GPU VRAM via nvidia-smi and apply as --vram ceiling")
    parser.add_argument("--family", metavar="PATTERN", help="Filter by model family")
    parser.add_argument("--quant", metavar="PATTERN", help="Filter to models with at least one matching quantization")
    parser.add_argument("--min-context", metavar="N", type=int, dest="min_context", help="Filter to models with at least one variant with context ≥ N tokens")
    parser.add_argument("--local-only", action="store_true", dest="local_only", help="Show only pullable models; exclude cloud-only registry entries")
    parser.add_argument("--cloud-only", action="store_true", dest="cloud_only", help="Show only cloud-only registry entries (not pullable via ollama)")
    parser.add_argument("--sort", default="pulls", choices=["pulls", "name", "tags", "updated", "trending", "size", "pulls-per-tag", "velocity"],
                        help="Sort field (default: pulls; pulls-per-tag surfaces concentrated models; velocity ranks by pulls/day since last update)")
    parser.add_argument("--trending-namespace", action="store_true", dest="trending_namespace",
                        help="Rank publishers by pull momentum vs --compare (default: HEAD~1)")
    parser.add_argument("--namespace-stats", metavar="PATTERN", nargs="?", const="__from_namespace__", dest="namespace_stats",
                        help="Summarize a publisher and list its models; use either --namespace PATTERN --namespace-stats or --namespace-stats PATTERN")
    parser.add_argument("--catalog-history", action="store_true", dest="catalog_history",
                        help="Show catalog-wide pull totals over git history with a sparkline panel")
    parser.add_argument("--compare", metavar="REF", default="HEAD~1", help="Baseline git ref for --sort trending and --trending-namespace")
    try:
        _rows = os.get_terminal_size().lines
    except OSError:
        _rows = 24
    _default_limit = max(5, _rows - 14)
    parser.add_argument("--limit", "-n", type=int, default=_default_limit,
                        help=f"Max results (0 = all, default: terminal rows − 14, currently {_default_limit})")
    parser.add_argument("--show", metavar="SLUG", help="Show full detail for a model")
    parser.add_argument("--like", metavar="SLUG", help="Show models related/similar to SLUG")
    parser.add_argument("--diff", metavar="REF", help="Show models added/removed since REF (git ref or YYYY-MM-DD)")
    parser.add_argument("--new-today", action="store_true", help="Shortcut for --diff HEAD~1: models added/removed since last snapshot")
    parser.add_argument("--history", metavar="SLUG", help="Show pull-count history for one model with a sparkline panel")
    parser.add_argument("--commits", metavar="N", type=int, default=30, help="Number of snapshots to scan for history views (default: 30)")
    parser.add_argument("--installed", metavar="FILE", nargs="?", const="__auto__", help="Recommend models based on 'ollama list' output")
    parser.add_argument("--stats", action="store_true", help="Show catalog summary statistics")
    parser.add_argument("--format", choices=["json", "tsv"], dest="format", default=None,
                        help="Emit machine-readable output for piping and automation; sparkline/chart panels appear only in TUI output")
    args = parser.parse_args()

    if args.new_today:
        args.diff = "HEAD~1"

    vram_gb = args.vram
    if args.fits_local:
        detected = None
        try:
            result = subprocess.run(["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"], capture_output=True, text=True)
            if result.returncode == 0 and result.stdout.strip():
                detected = max(float(x.strip()) for x in result.stdout.splitlines()) / 1024
        except FileNotFoundError:
            detected = None
        if detected is None:
            console.print("[yellow]--fits-local: could not detect GPU VRAM via nvidia-smi. Use --vram N instead.[/yellow]")
        else:
            vram_gb = detected
            console.print(f"[dim]Detected {detected:.0f}GB VRAM — filtering to models that fit[/dim]")

    size_min = size_max = None
    if args.size:
        try:
            size_min, size_max = parse_size_arg(args.size)
        except argparse.ArgumentTypeError as e:
            parser.error(str(e))

    if args.history:
        entries = load_history_for_slug(args.history, max_commits=args.commits)
        if not entries:
            console.print(f"[red]No history found for '{args.history}'.[/red]")
            return
        chrono = list(reversed(entries))
        pulls_values = [e["pulls"] for e in chrono]
        console.print(Panel(
            f"[bold cyan]{args.history}[/bold cyan]  [dim]{len(entries)} snapshot{'s' if len(entries) != 1 else ''}[/dim]\n\n"
            f"{sparkline(pulls_values)}\n\n"
            f"[dim]Total change over period: {fmt_delta(pulls_values[-1] - pulls_values[0] if len(pulls_values) >= 2 else 0)}[/dim]",
            title="Pull count history",
            border_style="cyan",
        ))
        table = Table(box=box.SIMPLE_HEAD, expand=True)
        table.add_column("Date", style="dim", no_wrap=True, min_width=10)
        table.add_column("Commit", style="dim", no_wrap=True, min_width=8)
        table.add_column("Pulls", justify="right", style="yellow", no_wrap=True, min_width=8)
        table.add_column("Δ", justify="right", no_wrap=True, min_width=8)
        for i, e in enumerate(chrono):
            delta_str = "[dim]—[/dim]" if i == 0 else fmt_delta(e["pulls"] - chrono[i - 1]["pulls"])
            table.add_row(e["date"], e["commit"], fmt_pulls(e["pulls_text"]) if e["pulls_text"] else f"{e['pulls']:,}", delta_str)
        console.print(table)
        return

    if args.catalog_history:
        show_catalog_history(max_commits=args.commits, fmt=args.format)
        return

    models, metadata = load_models(args.ref)
    total_catalog = len(models)

    if args.stats:
        show_stats(models, metadata)
        return

    if args.namespace_stats:
        if args.namespace_stats not in (True, "__from_namespace__"):
            target_namespace = args.namespace_stats
        elif args.namespace:
            target_namespace = args.namespace
        elif args.trending_namespace:
            rows, _ = _build_namespace_leaderboard_rows(models, args.compare)
            if not rows:
                console.print("[red]No namespaces available for --namespace-stats.[/red]")
                return
            target_namespace = rows[0]["namespace"]
            if not args.format:
                console.print(f"[dim]Using top trending namespace: {target_namespace}[/dim]")
        else:
            parser.error("--namespace-stats requires --namespace PATTERN, a PATTERN argument, or --trending-namespace")
        show_namespace_stats(models, target_namespace, fmt=args.format)
        return

    if args.trending_namespace:
        show_namespace_leaderboard(models, compare_ref=args.compare, limit=args.limit, fmt=args.format)
        return

    if args.diff:
        show_diff(models, args.diff, fmt=args.format)
        return

    if args.installed is not None:
        show_installed_recommendations(models, args.installed, fmt=args.format)
        return

    if args.dark_matter:
        show_dark_matter(models, args.limit, enrich=args.enrich, fmt=args.format)
        return

    if args.like:
        show_like(models, args.like)
        return

    if args.show:
        show_detail(models, args.show, all_models=models, enrich=args.enrich)
        return

    if args.sort == "trending":
        prev_pulls = load_pulls_snapshot(args.compare)
        if not prev_pulls:
            console.print(f"[yellow]No pull data at {args.compare} — falling back to sort: pulls[/yellow]")
            args.sort = "pulls"
        else:
            for m in models:
                prev = prev_pulls.get(m["slug"], 0)
                m["pulls_delta"] = m.get("pulls", 0) - prev
                m["pulls_delta_pct"] = m["pulls_delta"] / prev * 100 if prev > 0 else None

    filter_parts = []
    if args.search:
        scope = f"/{args.field}" if args.field != "all" else ""
        filter_parts.append(f"search={args.search}{scope}")
    if args.caps:
        filter_parts.append(f"caps={args.caps}")
    if args.type:
        filter_parts.append(f"type={args.type}")
    if args.namespace:
        filter_parts.append(f"namespace={args.namespace}")
    if args.tag:
        filter_parts.append(f"tag={args.tag}")
    if args.size:
        filter_parts.append(f"size={args.size}GB")
    if args.new:
        filter_parts.append(f"new≤{args.new}d")
    if args.stale:
        filter_parts.append(f"stale≥{args.stale}d")
    if args.min_tags:
        filter_parts.append(f"min-tags≥{args.min_tags}")
    if args.well_described:
        filter_parts.append("well-described")
    if vram_gb is not None:
        filter_parts.append(f"fits-local({vram_gb:.0f}GB)" if args.fits_local else f"vram≤{vram_gb}GB")
    if args.family:
        filter_parts.append(f"family={args.family}")
    if args.quant:
        filter_parts.append(f"quant={args.quant}")
    if args.min_context:
        filter_parts.append(f"context≥{args.min_context}")
    if args.local_only:
        filter_parts.append("local-only")
    if args.cloud_only:
        filter_parts.append("cloud-only")

    filtered = apply_filters(
        models, search=args.search, field=args.field, caps=args.caps,
        model_type=args.type, tag_pattern=args.tag,
        size_min=size_min, size_max=size_max, new_days=args.new,
        stale_days=args.stale, min_tags=args.min_tags, well_described=args.well_described,
        namespace=args.namespace, vram_max=vram_gb,
        family=args.family, quant=args.quant, min_context=args.min_context,
        local_only=args.local_only, cloud_only=args.cloud_only,
    )
    sorted_models = apply_sort(filtered, args.sort)
    if args.format:
        emit_format(sorted_models, args.format, limit=args.limit)
    else:
        show_list(sorted_models, args.limit, new_days=args.new, sort_field=args.sort,
                  filter_parts=filter_parts, total_catalog=total_catalog,
                  compare_ref=args.compare if args.sort == "trending" else "", vram_gb=vram_gb)


if __name__ == "__main__":
    main()
