#!/usr/bin/env sh
set -eu

site_config="${TAILSAFE_SITE_CONFIG:-/input/site.json}"
generated_dir="${TAILSAFE_GENERATED_DIR:-/generated}"

mkdir -p "$generated_dir/bin"

export TAILSAFE_BACKREST_GENERATED_DIR="${TAILSAFE_BACKREST_GENERATED_DIR:-$generated_dir}"
python /app/scripts/generate_backrest_config.py "$site_config" "$generated_dir/backrest-config.json"
/app/scripts/generate_htpasswd.sh \
  "$generated_dir/rest-server-backup.htpasswd" \
  "${TAILSAFE_BACKUP_HTTP_USER}" \
  "${TAILSAFE_BACKUP_HTTP_PASSWORD}" \
  "$generated_dir/rest-server-maint.htpasswd" \
  "${TAILSAFE_MAINT_HTTP_USER}" \
  "${TAILSAFE_MAINT_HTTP_PASSWORD}"

cp /app/scripts/preflight.sh "$generated_dir/bin/preflight.sh"
chmod +x "$generated_dir/bin/preflight.sh"
