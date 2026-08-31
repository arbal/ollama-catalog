## 2024-05-18 - Better Empty States in CLI
**Learning:** Terminal UIs (like those built with Rich) often render empty state fallback content poorly if left unhandled (e.g. producing an empty table structure which feels broken).
**Action:** Replace empty tables with styled panels with clear failure conditions, but make sure to *not* intercept machine-readable formatting options like JSON/TSV which still need deterministic empty structures.
