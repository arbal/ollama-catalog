## 2026-04-16 - Path Traversal Vulnerability in Model URL Generation
**Vulnerability:** The model slug is incorporated into URLs directly without path traversal protection or full encoding. A malicious user might craft a slug like "huihui_ai/../admin" which could manipulate the request path.
**Learning:** Explicitly validate and reject traversal sequences (e.g., `..`) before URL-encoding, as `urllib.parse.quote` does not encode period (`.`) characters by default, meaning path traversal sequences survive encoding.
**Prevention:** Validate input to reject '..' when constructing URL paths from user-controlled values like slugs, and ensure all user data is safely URL-encoded.
