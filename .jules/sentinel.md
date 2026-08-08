## 2024-05-24 - Fix path traversal in model URLs
**Vulnerability:** The model slug is passed directly into a constructed URL without encoding or path traversal validation.
**Learning:** Always URL-encode user-controlled values (like model slugs) when constructing URLs. Use 'urllib.parse.quote' with 'safe="/"' to preserve namespace slashes.
**Prevention:** Ensure explicit checks for path traversal sequences like '..' and always encode parameters used in URLs.
