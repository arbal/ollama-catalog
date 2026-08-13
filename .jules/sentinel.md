## 2025-05-24 - Path Traversal Prevention in URL Construction
**Vulnerability:** The scraper lacked explicit prevention for path traversal in the construction of remote API URLs, potentially leading to SSRF or fetching unintended endpoints if a malicious or malformed slug was provided (e.g., `../foo`).
**Learning:** `urllib.parse.quote` with `safe="/"` alone does not sanitize `..` sequences, as `.` is a safe character in URLs. Thus, manual validation to reject `..` is necessary alongside URL encoding to prevent path traversal fully.
**Prevention:** Always validate user-controlled paths or slugs by explicitly rejecting directory traversal sequences (`..`) before URL-encoding and assembling network requests.
