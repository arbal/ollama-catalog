
## 2025-02-14 - Prevent Path Traversal in Ollama Catalog
**Vulnerability:** The `ModelScraper` class constructed URLs for fetching model details by directly interpolating user-supplied or discovered model slugs without validating for path traversal sequences or performing URL encoding.
**Learning:** `urllib.parse.quote` does not encode periods (`.`) by default, so it alone doesn't prevent path traversal in URLs if a library blindly appends `../` strings.
**Prevention:** Explicitly block `..` sequences by validating strings before passing them to URL encoders, and always use `urllib.parse.quote` for user-supplied string interpolation in URL paths.
