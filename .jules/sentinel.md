## 2025-05-18 - Fix Path Traversal and Missing URL Encoding in ModelScraper
**Vulnerability:** The model slug from user input was directly inserted into URLs without validation or encoding, allowing path traversal (e.g. `../../etc/passwd`) and special character injection.
**Learning:** `urllib.parse.quote` does not encode `.` by default, so explicit validation against `..` is necessary to prevent path traversal even when encoding is used. Unvalidated parameters concatenated into URLs are a risk.
**Prevention:** Always validate external inputs explicitly against traversal sequences and properly URL encode them before constructing HTTP requests.
