## 2026-09-04 - Argument Injection in Git Show
**Vulnerability:** Argument injection via user-provided git refs in `subprocess.run(["git", "show", f"{ref}:{path}"])`.
**Learning:** Git interprets arguments starting with hyphens as options, even in the middle of a command. For `git show <ref>:<path>`, using the `--` end-of-options delimiter incorrectly causes Git to treat the string as a pathspec instead of a revision, making it ineffective.
**Prevention:** Explicitly validate that user-provided git refs do not start with a hyphen before passing them to subprocess commands.
