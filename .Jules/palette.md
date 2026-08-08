## 2024-08-08 - CLI Empty States
**Learning:** In CLI interfaces, displaying raw empty structures (like an empty table with 0 rows) can look broken or confusing. A dedicated empty state panel provides clearer feedback and a better user experience.
**Action:** Always prefer rendering a user-friendly `rich.panel.Panel` over an empty data table when search or filter results yield zero matches.
