## 2024-05-24 - CLI Empty State Polish
**Learning:** Using `rich` raw text instead of a `Panel` for empty states makes errors unnoticeable and disrupts the visual structure of CLI outputs, especially when mixing rich Tables/Panels with standard text.
**Action:** When implementing UI improvements for empty states in a CLI utilizing `rich`, use `rich.panel.Panel` wrappers for "Not Found" messages to maintain visual consistency and clearly signal to the user that a query returned no results.
