## 2024-05-24 - Empty State Panels for CLI
**Learning:** Terminal UIs using `rich` shouldn't display empty tables with headers when searches yield zero results. It's confusing and feels broken.
**Action:** Always render a user-friendly `Panel` for empty states to provide clear feedback and actionable next steps.
