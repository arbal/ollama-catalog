## 2024-05-24 - Path Traversal in Ollama Catalog Scraper
**Vulnerability:** The model scraper allowed path traversal via `..` in the user-supplied slug, which was concatenated into the fetch URL.
**Learning:** `urllib.parse.quote` does not encode period (`.`) characters by default, so we must explicitly validate and block `..` sequences to prevent path traversal when URLs are constructed manually.
**Prevention:** Explicitly block `..` in slugs and properly URL encode all other values using `urllib.parse.quote` before constructing URLs. Also ensure URL construction occurs within a `try` block so exceptions can be handled securely.
