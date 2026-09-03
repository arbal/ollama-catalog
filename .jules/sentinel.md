## 2024-05-15 - OS Command Injection via Git Ref

**Vulnerability:**
The `explore_catalog.py` and `render_catalog.py` scripts execute Git commands using `subprocess.run(["git", "show", f"{ref}:{path}"])` and `subprocess.run(["git", "log", f"--before={date_str} 23:59:59", "-1", "--format=%H"])` where `ref` and `date_str` come directly from command-line arguments (like `--diff REF` or `--history REF`). Although `subprocess.run` with a list of arguments avoids shell injection, Git itself interprets command-line options starting with `--`. If a user supplies a `ref` like `--output=/tmp/pwned`, `git show --output=/tmp/pwned:out/models.jsonl` writes the output to `/tmp/pwned:out/models.jsonl`. This is an argument injection vulnerability.

**Learning:**
Even when bypassing the shell by using argument lists in `subprocess.run`, tools like Git evaluate leading dashes as options rather than positional arguments. This allows argument injection (often leading to file writes or command execution).

**Prevention:**
Always use the `--` end-of-options delimiter before passing untrusted inputs to commands that parse options, e.g., `["git", "show", "--", f"{ref}:{path}"]`.
