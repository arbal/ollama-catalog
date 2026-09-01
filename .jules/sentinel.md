## 2025-05-24 - Prevent Path Traversal and Unencoded Slugs in URL Construction
**Vulnerability:** Path traversal (e.g. `..`) and missing URL encoding in `detect_url` allowed unvalidated user input (`slug`) to manipulate the requested Ollama URLs.
**Learning:** `urllib.parse.quote` does not encode periods (`.`), which means explicit validation against `..` is necessary to prevent path traversal when constructing URLs with user-supplied slugs.
**Prevention:** Always validate against traversal sequences like `..` explicitly and URL-encode dynamic segments before string interpolation. Ensure URL generation is handled inside a try/except block that catches `ValueError`.
