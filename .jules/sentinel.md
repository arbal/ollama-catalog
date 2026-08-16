## 2024-08-16 - Prevent path traversal in URL generation
**Vulnerability:** The `detect_url` method constructed URLs directly from user-controlled model slugs without sanitizing or encoding, allowing path traversal (e.g. `../../`) and URL injection.
**Learning:** When using `urllib.parse.quote(slug, safe="/")`, period characters (`.`) are not encoded by default, so explicit validation for `..` is necessary to prevent path traversal when the sanitized slug is used in paths.
**Prevention:** Always validate against traversal sequences like `..` explicitly and URL-encode dynamically constructed paths.
