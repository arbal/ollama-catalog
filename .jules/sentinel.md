## 2024-05-18 - Git Argument Injection in Revision Parsing
**Vulnerability:** `subprocess.run` with `git show <ref>:<path>` is vulnerable to argument injection if `<ref>` starts with a hyphen, because git parses `<ref>:<path>` as an argument if it starts with `-`, and the `--` end-of-options delimiter changes interpretation from revision to pathspec.
**Learning:** You cannot use `--` to protect `git show <ref>:<path>`. Instead, you must explicitly reject references starting with `-`.
**Prevention:** Always validate that user-provided git revisions do not start with a hyphen before passing them to `git show <ref>:<path>`.
