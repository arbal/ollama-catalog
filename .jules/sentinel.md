## 2025-05-18 - Path Traversal Vulnerability in Slug Parsing
**Vulnerability:** The application constructed URLs using unvalidated, unencoded user input in `detect_url(slug)`, creating a path traversal vulnerability.
**Learning:** `urllib.parse.quote` does not encode the period (`.`) character by default. Explicit validation (`".." in slug`) is required to prevent path traversal before URL encoding, particularly in applications where route parameters are mapped directly to file systems or internal API endpoints.
**Prevention:** Always validate against directory traversal sequences like `..` explicitly prior to encoding when dealing with file paths or URLs, and consistently URL-encode user-controlled components using `urllib.parse.quote(..., safe="/")`.
