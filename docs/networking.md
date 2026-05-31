# Networking

TailSafe uses Tailscale to connect friend sites without exposing rest-server ports on the public internet. The deployment model is still **symmetric**, but the inbound side is now **peer-specific**:

For a first deployment walkthrough with concrete example values on both sides, use the [Setup guide](setup-guide.md). This page focuses on the network model behind that walkthrough.

- one **global outbound** Tailscale role (`tailscale-outbound`) per site
- one **endpoint trio per inbound peer** (`tailscale-endpoint-<peer>`, `rest-server-backup-<peer>`, `rest-server-maintenance-<peer>`)

On **your** site:

- the outbound role pushes your backups to one or more remote TailSafe endpoint hostnames
- each generated endpoint trio receives one friend's backup and maintenance traffic into its own isolated repository subdirectory

Repository URIs in the example stack are plain `rest:http://...` over Tailscale, not HTTPS terminated inside the Compose file. Traffic stays on the Tailscale mesh between authenticated nodes.

The example stack uses **userspace Tailscale** networking (no `NET_ADMIN` capability or `/dev/net/tun` device in Compose). Tailscale runs inside the container without host TUN setup.

## Base stack plus generated endpoints

`deploy/compose.example.yaml` now defines only the base services:

- `configurator`
- `tailscale-outbound`
- `backrest`

The inbound endpoint services are generated into `${BACKREST_DATA_ROOT}/generated/compose.endpoints.yaml` from `config/site.json`. Run Compose with **both** files after the configurator has generated the fragment.

## Operator prerequisite

Before backups can flow, friends must coordinate tailnet membership, auth keys, and ACLs so that:

- this site's `tailscale-outbound` node can reach every `outboundRemotes[].endpointHostname` over Tailscale
- each generated `tailscale-endpoint-<peer>` node can join the corresponding friend's tailnet
- rest-server ports `8000` and `8001` on every endpoint hostname are reachable from the appropriate remote outbound node

Coordinate the endpoint hostnames that appear in `inboundPeers[]` with the hostnames your friends embed in their outbound `backupUri` and `maintenanceUri` values.

Create auth keys from the [Tailscale auth keys page](https://login.tailscale.com/admin/settings/keys).

ACL guidance for a one-friend rollout:

- allow your outbound node to reach your friend's endpoint hostname on ports `8000` and `8001`
- allow your friend's outbound node to reach your endpoint hostname on ports `8000` and `8001`
- do this in both directions before expecting scheduled backups or maintenance to succeed

## Auth key provenance

Each site still owns both directions locally, but the auth keys come from different tailnet admins:

| Role | Auth key | Issued by |
| --- | --- | --- |
| Outbound (`tailscale-outbound`) | `TS_OUTBOUND_AUTHKEY` | **This site's** tailnet admin — joins your own tailnet so Backrest can reach remote endpoints |
| Endpoint (`tailscale-endpoint-<peer>`) | `TS_ENDPOINT_AUTHKEY_<PEER>` | **That friend** — joins their tailnet so their outbound node can reach your rest-server ports |

Your friends do the same in reverse: they issue their own outbound key locally and use one key from you for each endpoint they host on your behalf.

## Outbound role

The **outbound** role on your site initiates backup and maintenance traffic toward remote TailSafe stacks.

- Container: `tailscale-outbound`
- Auth key: `TS_OUTBOUND_AUTHKEY` in `.env`
- Hostname: `TS_OUTBOUND_HOSTNAME` in `.env`
- Backrest shares this container's network namespace via `network_mode: service:tailscale-outbound`

Backrest uses the outbound Tailscale interface to reach the remote endpoint hostnames defined in `outboundRemotes[]`. It does not serve repository traffic to other sites through this role.

## Inbound endpoint trios

Each `inboundPeers[]` entry generates a dedicated endpoint trio on your site:

- `tailscale-endpoint-<peer>`
- `rest-server-backup-<peer>`
- `rest-server-maintenance-<peer>`

Every trio gets:

- its own Tailscale auth key and hostname
- its own backup and maintenance htpasswd files
- its own repository storage root at `${REPO_DATA_ROOT}/<repositorySubdir>`

The endpoint exposes two rest-server listeners on that peer-specific Tailscale hostname:

| Port | Service | Mode |
| --- | --- | --- |
| `8000` | `rest-server-backup-<peer>` | Append-only backups |
| `8001` | `rest-server-maintenance-<peer>` | `check`, `forget`, and `prune` |

Friends connect to these ports using the plain `rest:http://user:password@<endpoint-hostname>:<port>/<remote-id>` URIs defined in their `outboundRemotes[]`.

## UI exposure

Backrest serves its web UI on port `9898` inside the outbound Tailscale container's network namespace. In the example deployment, Compose publishes that port only on the loopback interface:

```yaml
ports:
  - "127.0.0.1:${BACKREST_BIND_PORT}:9898"
```

Open `http://127.0.0.1:9898` (or your chosen `BACKREST_BIND_PORT`) from the Synology host or via SSH port forwarding to browse snapshots and run restores. The UI is not exposed on all interfaces by default.

The example `config/site.example.json` still sets `"auth": { "disabled": true }`, so Backrest UI login is off by default. That is tolerable in the example because the UI is bound to localhost only; if you expose Backrest more broadly, enable Backrest auth or restrict access another way.

## Startup timing

Compose `depends_on` with `condition: service_started` ensures the Tailscale host container is running before Backrest or a generated rest-server starts. It does **not** wait for Tailscale to finish joining the mesh.

After a cold start:

- the first scheduled backup may fail if `tailscale-outbound` is not fully connected yet
- a friend's first inbound attempt may fail if their corresponding `tailscale-endpoint-<peer>` node is not fully connected yet

Retry the operation manually or wait for the next scheduled run once Tailscale shows the node as connected.

## Preflight scope

Backup plans run `preflight.sh` before each snapshot. The current implementation checks that configured source paths exist locally and that `RESTIC_REPOSITORY_PASSWORD` is set. It does not probe Tailscale connectivity or test whether remote rest-server endpoints are reachable; those failures appear when restic attempts the backup or maintenance operation.
