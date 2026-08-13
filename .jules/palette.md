## 2024-05-28 - Terminal CLI Empty States
**Learning:** Users often encounter empty states in CLI tools that render broken or empty tables, causing confusion. Implementing a clear, helpful Panel with actionable advice improves usability significantly.
**Action:** Always provide dedicated, visually distinct empty states (e.g. using `rich.panel.Panel`) instead of rendering empty structures when queries return zero results.
