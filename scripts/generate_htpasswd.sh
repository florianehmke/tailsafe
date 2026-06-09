#!/usr/bin/env sh
set -eu

write_pair() {
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
}

if [ "$#" -eq 1 ]; then
  manifest_path="$1"
  python3 - "$manifest_path" <<'PY'
import json
import os
import subprocess
import sys

with open(sys.argv[1], "r", encoding="utf-8") as handle:
    manifest = json.load(handle)

for peer in manifest.get("peers", []):
    backup_file = peer["backupHtpasswdPath"]
    maintenance_file = peer["maintenanceHtpasswdPath"]

    os.makedirs(os.path.dirname(backup_file), exist_ok=True)
    os.makedirs(os.path.dirname(maintenance_file), exist_ok=True)

    subprocess.run(
        ["htpasswd", "-Bbc", backup_file, peer["backupUser"], peer["backupPassword"]],
        check=True,
    )
    subprocess.run(
        [
            "htpasswd",
            "-Bbc",
            maintenance_file,
            peer["maintenanceUser"],
            peer["maintenancePassword"],
        ],
        check=True,
    )
    os.chmod(backup_file, 0o600)
    os.chmod(maintenance_file, 0o600)
PY

  exit 0
fi

if [ "$#" -ne 6 ]; then
  echo "usage: generate_htpasswd.sh <manifest.json> | <backup-file> <backup-user> <backup-pass> <maint-file> <maint-user> <maint-pass>" >&2
  exit 2
fi

write_pair "$1" "$2" "$3" "$4" "$5" "$6"
