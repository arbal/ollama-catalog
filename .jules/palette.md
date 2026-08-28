## 2023-10-25 - Improve CLI Empty State UX
**Learning:** For CLI interfaces using the `rich` library, rendering a `Panel` instead of an empty table or raw text significantly improves the empty state UX by providing a visually distinct and helpful message.
**Action:** Always prefer rendering a user-friendly `rich.panel.Panel` when displaying empty state results (e.g., searches yielding no matches) in terminal UIs.
