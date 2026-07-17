#!/usr/bin/env bash
set -euo pipefail

repo_root=$(git rev-parse --show-toplevel)
hooks_dir=$(git rev-parse --git-path hooks)
checker="$repo_root/scripts/check-public-catalog.sh"
managed_marker="# ollama-catalog-public-gate"

install_hook() {
  local name=$1
  local mode=$2
  local target="$hooks_dir/$name"
  local preserved_hook=""

  if [[ -f "$target" ]] && ! grep --fixed-strings --quiet "$managed_marker" "$target"; then
    preserved_hook="${target}.ollama-catalog-original"
    if [[ -e "$preserved_hook" ]]; then
      echo "refusing to overwrite existing preserved hook: $preserved_hook" >&2
      return 1
    fi
    mv "$target" "$preserved_hook"
  fi

  cat >"$target" <<EOF
#!/usr/bin/env bash
set -euo pipefail
$managed_marker
if [[ -n "$preserved_hook" && -x "$preserved_hook" ]]; then
  "$preserved_hook" "\$@"
fi
"$checker" "$mode"
EOF
  chmod +x "$target"
}

install_hook pre-commit --staged
install_hook pre-push artifacts
printf 'Installed public catalog checks in %s\n' "$hooks_dir"
