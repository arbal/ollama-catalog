## 2025-02-27 - [URL Injection via Unescaped Model Slug]
**Vulnerability:** Path traversal and Server-Side Request Forgery (SSRF) risk in URL generation via unescaped model slugs.
**Learning:** The application constructed external URLs by directly concatenating user-provided or externally-sourced strings (slugs). This allowed malicious payloads like `../../../../etc/passwd` or query parameter injections to modify the intended request path.
**Prevention:** Always URL-encode dynamic, untrusted path components using `urllib.parse.quote()` before interpolation. Use `safe="/"` when namespace-like slashes are expected and safe.
