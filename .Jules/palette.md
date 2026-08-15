## 2026-08-15 - Empty States in CLI
**Learning:** Displaying empty tables for search queries with no results creates a poor user experience as it looks like a rendering bug rather than a successful query with zero matches.
**Action:** Used `rich.panel.Panel` to explicitly communicate the empty state and reiterate the active filters, providing helpful context to the user.
