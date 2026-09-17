## 2026-09-17 - Fix git argument injection in git_show
**Vulnerability:** The `git_show` function passed a user-supplied `ref` string directly to `subprocess.run` without checking if it starts with a hyphen, which allows argument injection (e.g., using `--output=...` instead of a revision).
**Learning:** Even when `subprocess.run` is used with a list of arguments (which prevents shell injection), passing unsanitized user strings to commands that accept positional arguments can still lead to argument injection if the string starts with a hyphen and the command doesn't use the `--` end-of-options delimiter.
**Prevention:** Always validate that user-supplied revision references do not start with a hyphen, or use the `--` delimiter if supported by the specific git command invocation.
