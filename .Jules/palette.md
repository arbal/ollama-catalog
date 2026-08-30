## 2026-08-30 - Enhance empty state in CLI table
**Learning:** Returning an empty table with headers when search results are empty can be confusing and provides a poor UX, as it is not clear if there are actually 0 results or if something failed. It is better to show an explicit No results found message for clarity.
**Action:** Render a user-friendly rich.panel.Panel when displaying empty state results in CLI.
