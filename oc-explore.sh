#!/usr/bin/env bash
cd "$(dirname "$(realpath "$0")")"
export _OC_PROG="$(basename "$0")"
exec python3 scripts/explore_catalog.py "$@"
