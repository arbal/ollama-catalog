## 2026-04-16 - Prevent Argument Injection in git show
**Vulnerability:** User-provided inputs passed directly into git commands (e.g., `ref` in `git show <ref>:<path>`) are vulnerable to argument injection if they start with a hyphen.
**Learning:** The `--` end-of-options delimiter is not universally safe because `git show` treats the subsequent string as a pathspec instead of a revision.
**Prevention:** Explicitly validate that user-provided arguments intended to be revisions do not start with a hyphen.
