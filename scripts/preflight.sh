#!/usr/bin/env sh
set -eu

if [ "$#" -lt 2 ]; then
  echo "usage: preflight.sh <source-id> <path> [<path> ...]" >&2
  exit 2
fi

source_id="$1"
shift

: "${RESTIC_REPOSITORY_PASSWORD:?RESTIC_REPOSITORY_PASSWORD must be set}"

for path in "$@"; do
  if [ ! -e "$path" ]; then
    echo "[$source_id] missing backup path: $path" >&2
    exit 1
  fi
done
