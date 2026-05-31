#!/usr/bin/env bash
set -euo pipefail

if command -v docker >/dev/null 2>&1; then
  container_bin="docker"
  compose_cmd=(docker compose)
elif command -v podman >/dev/null 2>&1; then
  container_bin="podman"
  compose_cmd=(podman compose)
else
  echo "docker or podman is required for smoke:configurator" >&2
  exit 1
fi

if ! command -v curl >/dev/null 2>&1; then
  echo "curl is required for smoke:configurator" >&2
  exit 1
fi

cleanup() {
  "$container_bin" rm -f tailsafe-rest-auth-test >/dev/null 2>&1 || true
}

trap cleanup EXIT

rm -rf .tmp/generated .tmp/rest-data .tmp/compose.env
mkdir -p .tmp/generated .tmp/rest-data
cp env.example .tmp/compose.env
touch .tmp/generated/rest-server-backup-stale.htpasswd
touch .tmp/generated/rest-server-maint-stale.htpasswd
"$container_bin" build -t tailsafe-configurator:test -f containers/configurator/Dockerfile .
"$container_bin" build -t tailsafe-rest-server:test -f containers/rest-server/Dockerfile .
"$container_bin" run --rm \
  --env-file env.example \
  -e TAILSAFE_SITE_CONFIG=/input/site.example.json \
  -e TAILSAFE_GENERATED_DIR=/generated \
  -v "$PWD/config:/input:ro" \
  -v "$PWD/.tmp/generated:/generated" \
  tailsafe-configurator:test

python -m json.tool .tmp/generated/backrest-config.json >/dev/null
test -s .tmp/generated/compose.endpoints.yaml
test -s .tmp/generated/rest-server-backup-friend-b.htpasswd
test -s .tmp/generated/rest-server-maint-friend-b.htpasswd
test -s .tmp/generated/rest-server-backup-friend-c.htpasswd
test -s .tmp/generated/rest-server-maint-friend-c.htpasswd
test ! -e .tmp/generated/htpasswd-manifest.json
test ! -e .tmp/generated/rest-server-backup-stale.htpasswd
test ! -e .tmp/generated/rest-server-maint-stale.htpasswd

TAILSAFE_COMPOSE_ENV_FILE=../.tmp/compose.env \
  "${compose_cmd[@]}" \
  --env-file env.example \
  -f deploy/compose.example.yaml \
  -f .tmp/generated/compose.endpoints.yaml \
  config >/dev/null

"$container_bin" run --rm --entrypoint sh \
  -v "$PWD/.tmp/generated:/generated:ro" \
  tailsafe-configurator:test \
  -c '
    set -eu
    grep -Eqi "Red Hat Universal Base Image|PLATFORM_ID=\"platform:el|^ID=\"?rhel" /etc/os-release
    htpasswd -vb /generated/rest-server-backup-friend-b.htpasswd backup-b change-me >/dev/null
    htpasswd -vb /generated/rest-server-maint-friend-b.htpasswd maint-b change-me >/dev/null
    htpasswd -vb /generated/rest-server-backup-friend-c.htpasswd backup-c change-me >/dev/null
    htpasswd -vb /generated/rest-server-maint-friend-c.htpasswd maint-c change-me >/dev/null
    ! htpasswd -vb /generated/rest-server-backup-friend-b.htpasswd backup-b wrong >/dev/null 2>&1
    ! htpasswd -vb /generated/rest-server-maint-friend-c.htpasswd maint-c wrong >/dev/null 2>&1
  '

"$container_bin" run -d --rm --name tailsafe-rest-auth-test \
  -p 127.0.0.1:18080:8000 \
  -e OPTIONS="--listen :8000" \
  -e PASSWORD_FILE=/generated/rest-server-backup-friend-b.htpasswd \
  -v "$PWD/.tmp/generated:/generated:ro" \
  -v "$PWD/.tmp/rest-data:/data" \
  tailsafe-rest-server:test >/dev/null

sleep 3

no_auth_status="$(curl -s -o /dev/null -w "%{http_code}" http://127.0.0.1:18080/)"
good_auth_status="$(curl -s -o /dev/null -w "%{http_code}" -u backup-b:change-me http://127.0.0.1:18080/)"
bad_auth_status="$(curl -s -o /dev/null -w "%{http_code}" -u backup-b:wrong http://127.0.0.1:18080/)"

test "$no_auth_status" = "401"
test "$good_auth_status" = "405"
test "$bad_auth_status" = "401"
