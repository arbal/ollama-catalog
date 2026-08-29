## 2024-05-15 - Improve empty state UI in CLI
**Learning:** Rendering an empty structural table when a search yields no results presents poor UX and feels broken. In a CLI environment using `rich`, it is much better to detect the empty state early and render a friendly, descriptive Panel (with feedback on applied filters) while preserving strict programmatic output formats.
**Action:** Always intercept empty datasets before rendering structural components like tables, and substitute them with a user-friendly empty state Panel when in human-readable mode.
