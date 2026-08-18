## 2024-05-24 - Empty States in CLI Tables
**Learning:** Returning empty lists or tables when search/filter returns zero results makes the UI feel broken and confusing, giving the user no actionable feedback in a TUI/CLI environment.
**Action:** When displaying collections via tables or lists that might end up empty, render a helpful empty state, such as a rich `Panel` explaining what happened.
