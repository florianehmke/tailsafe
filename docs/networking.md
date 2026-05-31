# Networking

TailSafe uses Tailscale to connect friend sites without exposing rest-server ports on the public internet. The deployment model is **symmetric**: each friend runs the **full** stack locally—configurator, both Tailscale roles (`tailscale-outbound` and `tailscale-endpoint`), Backrest, and both rest-server containers (`rest-server-backup` and `rest-server-maintenance`).

On **your** site:

- The **outbound** role pushes your backups to **your friend's** endpoint hostname.
- The **endpoint** role receives **your friend's** backups into your local repository storage.

Each site therefore owns both roles in its own `.env` and Compose file, even though outbound traffic always targets the remote friend's endpoint and inbound traffic always arrives at yours.

Repository URIs in the example stack are plain `rest:http://...` over Tailscale—not HTTPS terminated inside the Compose file. Traffic stays on the Tailscale mesh between authenticated nodes.

Both rest-server containers on each site mount the same `${REPO_DATA_ROOT}` path. Append-only backups and maintenance operations therefore target the same underlying restic repository storage.

The example stack uses **userspace Tailscale** networking (no `NET_ADMIN` capability or `/dev/net/tun` device in Compose). Tailscale runs inside the container without host TUN setup.

## Operator prerequisite

Before backups can flow, **both** sites must arrange tailnet membership, auth keys, and ACLs so that:

- each site's **outbound** node can reach the other site's **endpoint** hostname over Tailscale, and
- rest-server ports `8000` and `8001` on the endpoint hostname are reachable from the remote outbound node.

Coordinate hostname values (`TS_ENDPOINT_HOSTNAME` on each side) with the URIs in each friend's `config/site.json`.

## Auth key provenance

Each site runs the full stack, but the two Tailscale auth keys come from different tailnet admins:

| Role | Auth key | Issued by |
| --- | --- | --- |
| Outbound (`tailscale-outbound`) | `TS_OUTBOUND_AUTHKEY` | **This site's** tailnet admin — joins your own tailnet so Backrest can reach the friend's endpoint |
| Endpoint (`tailscale-endpoint`) | `TS_ENDPOINT_AUTHKEY` | **Your friend** — joins their tailnet so their outbound node can reach your rest-server ports |

Your friend does the same in reverse: they issue their own outbound key locally and use a key you provide for their endpoint role.

## Outbound role

The **outbound** role on your site initiates backup and maintenance traffic toward your friend.

- Container: `tailscale-outbound`
- Auth key: `TS_OUTBOUND_AUTHKEY` in `.env` (issued for this site's own tailnet)
- Hostname: `TS_OUTBOUND_HOSTNAME` in `.env`
- Backrest shares this container's network namespace via `network_mode: service:tailscale-outbound`

Backrest uses the outbound Tailscale interface to reach the remote friend's endpoint hostname (for example `friend-b-endpoint.ts.net`). It does not serve repository traffic to other sites through this role.

## Endpoint role

The **endpoint** role on your site receives your friend's backup and maintenance traffic.

- Container: `tailscale-endpoint`
- Auth key: `TS_ENDPOINT_AUTHKEY` in `.env` (issued by your friend for their tailnet)
- Hostname: `TS_ENDPOINT_HOSTNAME` in `.env` (this is the name your friend puts in their `site.json` URIs)
- Both rest-server containers share this network namespace via `network_mode: service:tailscale-endpoint`

The endpoint exposes two rest-server listeners on the Tailscale hostname:

| Port | Service | Mode |
| --- | --- | --- |
| `8000` | `rest-server-backup` | Append-only backups |
| `8001` | `rest-server-maintenance` | `check`, `forget`, and `prune` |

Friends connect to these ports using the plain `rest:http://user:password@<endpoint-hostname>:<port>/<remote-id>` URIs defined in `config/site.json`.

## UI exposure

Backrest serves its web UI on port `9898` inside the outbound Tailscale container's network namespace. In the example deployment, Compose publishes that port only on the loopback interface:

```yaml
ports:
  - "127.0.0.1:${BACKREST_BIND_PORT}:9898"
```

Open `http://127.0.0.1:9898` (or your chosen `BACKREST_BIND_PORT`) from the Synology host—or via SSH port forwarding—to browse snapshots and run restores. The UI is not exposed on all interfaces by default.

The example `config/site.example.json` sets `"auth": { "disabled": true }`, so Backrest UI login is off by default. That is tolerable in the example because the UI is bound to localhost only; if you expose Backrest more broadly, enable Backrest auth or restrict access another way.

## Startup timing

Compose `depends_on` with `condition: service_started` ensures the Tailscale **host container** is running before Backrest or rest-server starts. It does **not** wait for Tailscale to finish joining the mesh.

After a cold start, the first scheduled backup may fail if Backrest runs before outbound Tailscale connectivity is ready. Retry the backup manually or wait for the next scheduled run once Tailscale shows the node as connected.

## Preflight scope

Backup plans run `preflight.sh` before each snapshot. The current implementation checks that configured source paths exist locally and that `RESTIC_REPOSITORY_PASSWORD` is set. It does not probe Tailscale connectivity or test whether the remote rest-server endpoints are reachable; those failures appear when restic attempts the backup or maintenance operation.
