## 2025-02-18 - Prevent path traversal in URL construction
**Vulnerability:** The `ModelScraper.detect_url` method in `src/ollama_catalog/model_scraper.py` used string concatenation to construct URLs from unsanitized `slug` strings, which allowed path traversal vulnerabilities.
**Learning:** `urllib.parse.quote` (with `safe="/"`) does not encode or sanitize `.` (period) characters by default, meaning path traversal sequences like `..` remain unchanged after encoding. Therefore, explicit traversal string checking must be performed in addition to URL encoding.
**Prevention:** Always validate and reject URLs containing sequence `..` before performing any URL-encoding when incorporating user input directly into paths. Ensure to use URL encoding on all parameterized string inputs.
