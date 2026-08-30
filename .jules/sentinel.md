## 2024-08-30 - Path Traversal Prevention
**Vulnerability:** URL construction using user-controlled slugs (e.g. `../`) without proper validation or encoding.
**Learning:** `urllib.parse.quote` doesn't encode `.` characters and needs explicit validation to prevent path traversal when constructing URLs.
**Prevention:** Always validate input to explicitly block `..` or similar traversal patterns before performing URL encoding.
