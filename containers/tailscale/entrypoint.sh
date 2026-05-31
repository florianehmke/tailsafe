#!/usr/bin/env sh
set -eu

state_dir="${TS_STATE_DIR:-/var/lib/tailscale}"
mkdir -p "$state_dir"

tailscaled --state="${state_dir}/tailscaled.state" --tun=userspace-networking &
daemon_pid="$!"

until tailscale up \
  --authkey="${TS_AUTHKEY}" \
  --hostname="${TS_HOSTNAME}" \
  --accept-dns=false; do
  if ! kill -0 "$daemon_pid" 2>/dev/null; then
    exit 1
  fi
  sleep 2
done

wait "$daemon_pid"
