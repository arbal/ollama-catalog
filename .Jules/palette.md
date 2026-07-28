## 2024-05-19 - Empty State Panels in CLI

**Learning:** When a CLI application (using rich) returns 0 results for a complex query or filter, simply not displaying a table or printing raw text can be jarring and doesn't tell the user *why* there were no results. Showing an explicit "Zero Results" panel and echoing back the exact filters applied provides immediate clarity and actionable context.

**Action:** Always prefer wrapping empty state messages in a `rich.panel.Panel` and include the applied filters/context whenever possible, rather than rendering empty structural elements like tables or plain text errors.
