## 2024-07-29 - Prevent path traversal in ModelScraper URLs
**Vulnerability:** The `detect_url` method in `ModelScraper` appended an unvalidated, user-controlled `slug` parameter directly to external URLs. This could allow for path traversal attacks via sequences like `../` or parameter injection if special characters weren't encoded.
**Learning:** Even internal helper methods creating outbound URLs need validation, especially when consuming external identifier strings (like slugs) that will dictate HTTP request paths.
**Prevention:** Explicitly validate inputs for traversal sequences (e.g., rejecting strings containing `..`) and properly encode dynamic URL segments using `urllib.parse.quote(slug, safe="/")`.
