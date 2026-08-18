## 2025-02-18 - Path Traversal via URL Slug
**Vulnerability:** The model scraper passes user-controlled slugs directly into the URL path without checking for traversal sequences like `..` or URL encoding the inputs.
**Learning:** `urllib.parse.quote` does not URL encode period (`.`) characters by default, requiring explicit validation checks against directory traversal strings (`..`) before URL construction.
**Prevention:** Always validate and reject path traversal sequences in URL-bound variables, and ensure inputs are properly URL encoded to safely handle special characters.
