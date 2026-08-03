## 2026-04-16 - Prevent Path Traversal in Ollama Catalog Model Slug

**Vulnerability:** The `detect_url` method constructed URLs by appending the `slug` variable directly without sanitization, allowing potential path traversal attacks through crafted user input (e.g., passing `"huihui_ai/../qwen"` into the search endpoint to request other resources).
**Learning:** `urllib.parse.quote` does not encode period (`.`) characters by default. Using it to build URL segments does not inherently prevent path traversal attacks.
**Prevention:** Explicitly validate and reject `..` in URL strings constructed from user input prior to calling `urllib.parse.quote`.
