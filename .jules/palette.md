## 2024-05-18 - Avoid Empty Tables in Rich Output
**Learning:** Using `rich` library to render an empty table when no models match a query provides a poor user experience. An empty list should be represented with a prominent and clear empty state message, for example using `rich.panel.Panel`, instead of drawing header/footer borders around empty rows.
**Action:** When a search query or filter yields zero results in a CLI application using `rich`, explicitly check the result length and render a user-friendly `Panel` with a descriptive message rather than displaying an empty table.
