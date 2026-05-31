#!/usr/bin/env sh
set -eu

if [ "$#" -ne 6 ]; then
  echo "usage: generate_htpasswd.sh <backup-file> <backup-user> <backup-pass> <maint-file> <maint-user> <maint-pass>" >&2
  exit 2
fi

backup_file="$1"
backup_user="$2"
backup_pass="$3"
maint_file="$4"
maint_user="$5"
maint_pass="$6"

mkdir -p "$(dirname "$backup_file")" "$(dirname "$maint_file")"
htpasswd -Bbc "$backup_file" "$backup_user" "$backup_pass"
htpasswd -Bbc "$maint_file" "$maint_user" "$maint_pass"
chmod 600 "$backup_file" "$maint_file"
