## 2024-08-23 - URL Encoding and Path Traversal in Scraper
**Vulnerability:** The scraper constructed URLs using string interpolation with unvalidated user input (`slug`), allowing both path traversal (`../`) and improper URL characters to be passed to requests.
**Learning:** `urllib.parse.quote` does not encode `.` by default, so explicit validation for `..` is needed to prevent path traversal, even when encoding is applied. Exceptions from validation must be gracefully caught.
**Prevention:** Always validate against traversal sequences and URL-encode dynamic path segments using `urllib.parse.quote(..., safe="/")`.
