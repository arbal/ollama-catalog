## 2025-05-24 - [Path Traversal in detect_url]
**Vulnerability:** The model scraper allowed path traversal vulnerabilities when processing model slugs (e.g. `../../../etc/passwd`). Furthermore, special characters were not properly URL-encoded.
**Learning:** `urllib.parse.quote` does not encode period (`.`) characters by default. Using it alone is not sufficient to prevent path traversal in URLs where the parameter controls part of the path.
**Prevention:** Always explicitly validate and reject traversal sequences (e.g., `if '..' in slug: raise ValueError(...)`) before or when using URL encoding.
