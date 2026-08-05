## 2024-05-24 - Improve Empty State UX in CLI Tools
**Learning:** Returning empty tables in terminal UIs can look broken or confusing to users when their search or filter yields no results.
**Action:** Always render a user-friendly empty state panel (e.g., using `rich.panel.Panel`) indicating no matches were found, and include the applied filters to provide context.
