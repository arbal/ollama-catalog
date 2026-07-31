## 2024-05-24 - Add friendly empty state for zero search results
**Learning:** Terminal UIs using libraries like `rich` can display empty tabular structures (like `Table` with only headers) when query results are empty, which can look broken or unhelpful. Providing an explicit empty state via a visual component like `Panel` improves clarity.
**Action:** Always check for empty results sets before rendering complex structural UI components (like tables) and render a distinct, helpful "no results" state instead.
