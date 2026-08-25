## 2025-02-27 - Path Traversal in Model Slugs
**Vulnerability:** The application was vulnerable to path traversal because user-controlled `slug` parameters were injected directly into URLs without validation or URL-encoding.
**Learning:** Always explicitly validate and reject sequence characters like `..` even when using `urllib.parse.quote`, because `quote` does not encode periods by default.
**Prevention:** Use explicit input validation and reject unsafe path traversal components.
