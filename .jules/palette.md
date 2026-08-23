## 2026-04-15 - Initial Journal
**Learning:** Initializing journal for Palette learnings.
**Action:** Ready to track UX and a11y findings.

## 2026-04-15 - Improve empty state rendering
**Learning:** Displaying empty tables or raw text for zero-result states provides a poor user experience. Using a `rich.panel.Panel` creates a consistent, visually distinct empty state that feels intentional.
**Action:** Always render a user-friendly Panel instead of empty tables or raw text when returning no results in CLI interfaces using 'rich'.
