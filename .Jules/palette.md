## 2024-05-15 - Empty State Panels in CLI UIs
**Learning:** Rendering an empty table structure when a user searches or filters a CLI dataset is unhelpful and makes the application feel broken or robotic. Displaying a clear, user-friendly empty state panel provides better context and actionable next steps.
**Action:** When implementing CLI interfaces using rich, always prefer rendering a descriptive `rich.panel.Panel` instead of raw text or empty tables when search or filter results yield no matches.
