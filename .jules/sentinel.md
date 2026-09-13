## 2026-09-13 - Git Command Argument Injection Prevention
**Vulnerability:** Argument injection vulnerability in `git show` where a user-provided git revision starting with a hyphen (e.g., `--help`) is parsed as a command option rather than a revision string.
**Learning:** Using `--` in `git show <ref>:<path>` causes git to interpret the string as a pathspec rather than a revision, failing the command.
**Prevention:** Explicitly validate that user-provided git references do not start with a hyphen before passing them to git commands.
