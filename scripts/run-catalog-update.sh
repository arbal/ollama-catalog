#!/usr/bin/env bash
set -euo pipefail

usage() {
  echo "usage: $0 [auto|incremental|full]" >&2
  echo "       $0 --print-mode [auto|incremental|full]" >&2
  exit 2
}

print_mode=false
if [[ "${1:-}" == "--print-mode" ]]; then
  print_mode=true
  shift
fi

[[ "$#" -le 1 ]] || usage
requested_mode="${1:-auto}"

case "$requested_mode" in
  auto)
    weekday="${CATALOG_UPDATE_DAY:-$(date -u +%u)}"
    case "$weekday" in
      1|4) mode=full ;;
      2|3|5|6|7) mode=incremental ;;
      *)
        echo "CATALOG_UPDATE_DAY must be an ISO weekday from 1 through 7" >&2
        exit 2
        ;;
    esac
    ;;
  incremental|full)
    mode="$requested_mode"
    ;;
  *)
    usage
    ;;
esac

if [[ "$print_mode" == true ]]; then
  printf '%s\n' "$mode"
  exit 0
fi

repo_root="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$repo_root"
printf 'Catalog update mode: %s\n' "$mode"

case "$mode" in
  full)
    ollama-catalog discover --full
    ollama-catalog fetch --refetch --reconcile
    ;;
  incremental)
    ollama-catalog discover
    ollama-catalog fetch
    ;;
esac

ollama-catalog sanitize
scripts/check-public-catalog.sh
