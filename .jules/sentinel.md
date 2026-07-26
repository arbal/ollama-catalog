## 2025-07-26 - URL Injection in Model Scraper
**Vulnerability:** URL injection/path traversal vulnerability in the `ModelScraper.detect_url` method. Untrusted user input (`slug`) was directly interpolated into the HTTP URL to `ollama.com` without proper URL-encoding.
**Learning:** External model catalog crawlers must sanitize untrusted identifiers before forming requests, as a maliciously crafted slug could manipulate the request path or inject arbitrary HTTP parameters.
**Prevention:** Always use standard URL-encoding functions like `urllib.parse.quote()` on untrusted URL components. If slashes are structurally meaningful (e.g., distinguishing namespaces), explicitly whitelist them using the `safe` parameter (e.g., `safe="/"`).
