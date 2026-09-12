## 2025-02-18 - Argument Injection in git show wrapper
**Vulnerability:** Argument injection via git revision string starting with a hyphen in `git_show` (`scripts/explore_catalog.py`).
**Learning:** Using `--` does not prevent argument injection when the argument is placed before it. In `git show {ref}:{path}`, the `{ref}` parameter could start with a `-` (like `-h`), which git interprets as an option, breaking the expected command format and potentially allowing malicious command execution.
**Prevention:** Explicitly validate that user-provided inputs used in shell commands do not start with a hyphen, or ensure they are placed after the `--` end-of-options delimiter if applicable.
