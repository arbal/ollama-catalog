## 2025-01-30 - CLI Empty States

**Learning:** Terminal CLI users appreciate well-formatted visual panels when queries return zero results, instead of raw text error lines.
**Action:** Replaced simple console.print("[red]Not found[/red]") error strings with rich `Panel` empty states to maintain visual consistency in scripts/explore_catalog.py
