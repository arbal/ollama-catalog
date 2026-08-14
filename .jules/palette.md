## 2025-02-14 - Empty State Polish
**Learning:** Displaying empty states as bare tables provides poor UX in CLIs because it looks like a rendering error.
**Action:** Use `rich.panel.Panel` instead of empty tables for CLI outputs with zero results to guide users gracefully.
