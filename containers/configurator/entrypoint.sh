#!/usr/bin/env sh
set -eu

site_config="${TAILSAFE_SITE_CONFIG:-/input/site.json}"
generated_dir="${TAILSAFE_GENERATED_DIR:-/generated}"
manifest_path="$(mktemp)"

cleanup() {
  rm -f "$manifest_path"
}

trap cleanup EXIT HUP INT TERM

mkdir -p "$generated_dir/bin"
rm -f \
  "$generated_dir"/rest-server-backup.htpasswd \
  "$generated_dir"/rest-server-maint.htpasswd \
  "$generated_dir"/rest-server-backup-*.htpasswd \
  "$generated_dir"/rest-server-maint-*.htpasswd

export TAILSAFE_BACKREST_GENERATED_DIR="${TAILSAFE_BACKREST_GENERATED_DIR:-$generated_dir}"
python /app/scripts/generate_backrest_config.py "$site_config" "$generated_dir/backrest-config.json"
python /app/scripts/generate_runtime_assets.py \
  "$site_config" \
  "$generated_dir/compose.endpoints.yaml" \
  "$manifest_path"
/app/scripts/generate_htpasswd.sh "$manifest_path"

cp /app/scripts/preflight.sh "$generated_dir/bin/preflight.sh"
chmod +x "$generated_dir/bin/preflight.sh"
