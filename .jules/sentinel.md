## 2024-09-09 - Prevent Git Argument Injection in git_show
**Vulnerability:** The `git_show` function executed `git show <ref>:<path>` where `<ref>` is user-controlled. If `<ref>` starts with a hyphen, Git could interpret it as a command-line option, leading to argument injection.
**Learning:** Using `--` as an end-of-options delimiter does not work in this specific Git context because `git show -- <ref>:<path>` causes Git to treat `<ref>:<path>` as a pathspec rather than a revision format.
**Prevention:** Explicitly validate that user-provided Git references do not start with a hyphen before passing them to Git subprocess calls.
