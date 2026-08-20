## 2024-08-20 - Prevent Path Traversal in Slugs
**Vulnerability:** Path traversal and missing URL encoding in user-controlled slugs allowed accessing arbitrary files and constructing invalid URLs.
**Learning:** Always URL-encode user input with `urllib.parse.quote`, and explicitly reject traversal sequences (`..`) as `quote` does not encode periods by default.
**Prevention:** Validate input for traversal patterns before encoding and constructing URLs.
