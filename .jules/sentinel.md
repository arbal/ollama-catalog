## 2025-05-24 - Fix Path Traversal in URL Construction
**Vulnerability:** The `ModelScraper` directly concatenated user-controlled slugs into URLs (e.g., `f"https://ollama.com/{slug}"`), creating path traversal (`../`) and HTTP injection risks.
**Learning:** When using `urllib.parse.quote(slug, safe="/")` to URL-encode user input, the period character (`.`) is not encoded by default. Therefore, an explicit check for `..` is still required to prevent path traversal prior to encoding.
**Prevention:** Explicitly reject slugs containing `..` and always use URL encoding for dynamically constructed URLs. Ensure validation methods raise exceptions caught securely by the caller.
