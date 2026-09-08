## 2024-10-24 - Prevent Argument Injection in git show
**Vulnerability:** Argument injection risk in `subprocess.run` where a user-provided Git ref could start with a hyphen, causing Git to interpret it as an option rather than a revision, because `--` cannot be used with the `<ref>:<path>` syntax.
**Learning:** Using `--` (end-of-options) delimiter does not work for `<ref>:<path>` arguments in `git show` as Git interprets it as a pathspec instead.
**Prevention:** Explicitly validate that user-provided git references do not start with a hyphen when they must be combined with a path using the `<ref>:<path>` syntax.
