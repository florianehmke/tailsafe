# Configuration

TailSafe separates published examples from the files you actually run at each site. Copy the example files, fill in secrets locally, and keep production copies out of version control.

If you are doing a first install, follow [Agent-assisted install](agent-install.md) first. This page is the field reference and lifecycle reference for the generated files.

## User-owned files

These files define how a live TailSafe deployment behaves. They are not committed by the project; you create and maintain them on each Synology (or other host).

### `deploy/compose.yaml`

Your site-local **base** Compose file. Start from `deploy/compose.example.yaml` and adjust image tags, volume paths, and local ports for your environment. This base file wires together the configurator, the outbound Tailscale node, and Backrest.

The base file also carries outbound runtime wiring that changes between releases (for example the userspace proxy listener and Backrest proxy environment variables). Existing deployments keep their own `deploy/compose.yaml`; when upstream changes that wiring, refresh your local copy from `deploy/compose.example.yaml` and merge your paths or ports. Bumping `TAILSAFE_VERSION` in `.env` alone is not enough, and rerunning the configurator or regenerating `${BACKREST_DATA_ROOT}/generated` alone is not enough either, if the base compose file is stale.

The inbound endpoint services are now generated dynamically into `${BACKREST_DATA_ROOT}/generated/compose.endpoints.yaml` based on `config/site.json`.

### `.env`

Environment variables consumed by Compose and also passed through to the configurator. For a first pair, start from `env.one-friend.example`; use `env.example` for the advanced multi-friend reference layout. It holds Tailscale auth keys, per-remote and per-peer HTTP passwords, the restic repository password, filesystem paths (`BACKREST_DATA_ROOT`, `REPO_DATA_ROOT`, `USERDATA_ROOT`, and related roots), the path to your site file (`SITE_CONFIG_PATH`), and the upstream Tailscale container tag (`TAILSCALE_DOCKER_TAG`, for example `stable`).

### `config/site.json`

The site configuration consumed by the configurator to generate `backrest-config.json`, the inbound endpoint compose fragment, per-peer `tailscale-serve-<peer>.json` Serve configs, peer-specific htpasswd files, and related runtime material. For a first pair, start from `config/site.one-friend.example.json`; use `config/site.example.json` for the advanced multi-friend reference layout. Each site keeps its own copy with friend-specific remotes, inbound peers, schedules, sources, and Healthchecks.io URLs.

## Required secrets

Set these in `.env` before starting the stack. Never commit real values to the repository.

Create Tailscale auth keys from the [Tailscale auth keys page](https://login.tailscale.com/admin/settings/keys).

TailSafe now separates **outbound** credentials (what you need to reach a friend's TailSafe stack) from **inbound** credentials (what you define locally so a friend can reach yours).

| Variable pattern | Purpose |
| --- | --- |
| `TS_OUTBOUND_AUTHKEY` | Issue this for **this site's own tailnet**. Used by `tailscale-outbound` so Backrest can push backups to remote endpoint hostnames over Tailscale. |
| `TS_ENDPOINT_AUTHKEY_<PEER>` | Issue one per inbound friend. Each key comes from **that friend's** tailnet admin so the generated `tailscale-endpoint-<peer>` node can join their tailnet. |
| `TAILSAFE_REMOTE_BACKUP_HTTP_PASSWORD_<REMOTE>` | Password for the append-only backup URI you use when pushing to a specific remote TailSafe stack. Your friend gives you this value. |
| `TAILSAFE_REMOTE_MAINT_HTTP_PASSWORD_<REMOTE>` | Password for the maintenance URI you use when running `check`, `forget`, and `prune` against a specific remote TailSafe stack. Your friend gives you this value. |
| `TAILSAFE_INBOUND_BACKUP_HTTP_PASSWORD_<PEER>` | Password your local configurator writes into `rest-server-backup-<peer>.htpasswd`. You share this with that friend so they can push backups to you. |
| `TAILSAFE_INBOUND_MAINT_HTTP_PASSWORD_<PEER>` | Password your local configurator writes into `rest-server-maint-<peer>.htpasswd`. You share this with that friend so they can run maintenance against your endpoint. |
| `RESTIC_REPOSITORY_PASSWORD` | Encryption password for the restic repositories. Referenced in `site.json` and required by Backrest and restic tooling. |

Related non-secret variables must also be set:

| Variable pattern | Purpose |
| --- | --- |
| `TS_OUTBOUND_HOSTNAME` | Tailscale hostname registered by this site's outbound node (for example `tailsafe-outbound`). |
| `TS_ENDPOINT_HOSTNAME_<PEER>` | Tailscale hostname registered by the generated endpoint node for that inbound peer. Your friend targets this hostname in their outbound URIs. |
| `TAILSAFE_IMAGE_NAMESPACE` / `TAILSAFE_VERSION` | GHCR image namespace and pinned tag used by `deploy/compose.yaml` (see `env.example`). |
| `TAILSCALE_DOCKER_TAG` | Upstream Tailscale container tag used by `tailscale-outbound` and generated endpoint nodes (for example `stable`; see `env.example`). |
| Path roots (`BACKREST_DATA_ROOT`, `REPO_DATA_ROOT`, `USERDATA_ROOT`, and related) | Filesystem locations for generated assets, repository storage, userdata mounts, and Tailscale state. |

Legacy single-remote deployments remain supported during the migration window. If you still use the old `remote` schema, TailSafe falls back to `TS_ENDPOINT_AUTHKEY`, `TS_ENDPOINT_HOSTNAME`, `TAILSAFE_BACKUP_HTTP_*`, and `TAILSAFE_MAINT_HTTP_*`.

For every friend relationship in the new model, remember that the endpoint-key flow is two-way:

- you issue one endpoint key for your friend to join **your** tailnet
- your friend issues one endpoint key for you to join **their** tailnet

## Local-only vs exchanged values

| Category | Values |
| --- | --- |
| Local only | `TS_OUTBOUND_AUTHKEY`, host path roots, local bind port |
| Send to friend | endpoint auth key you issued for them, endpoint hostname they should target, inbound HTTP users/passwords |
| Receive from friend | endpoint auth key they issued for you, remote endpoint hostname/FQDN, remote HTTP users/passwords |
| Store securely | every auth key, HTTP password, `RESTIC_REPOSITORY_PASSWORD`, Backrest UI credential |

### Backrest UI auth lifecycle

- localhost-only UI can tolerate `auth.disabled: true`
- LAN exposure should enable Backrest auth
- Backrest UI passwords are not recoverable from the stored hash
- password reset uses Backrest's own password-hash format, not a raw Apache htpasswd bcrypt string

### First-install vs upgrade

- greenfield installs should follow [Agent-assisted install](agent-install.md); use `env.one-friend.example` and `config/site.one-friend.example.json` as the starting templates
- existing deployments must compare their live `deploy/compose.yaml` with `deploy/compose.example.yaml` when release wiring changes
- rerunning the configurator alone does not pick up stale base compose wiring
- version pin bumps and multi-site migration both require an explicit regeneration and bring-up pass

## HTTP credential coordination

The multi-site model deliberately separates the two directions:

1. **Inbound peer credentials** live under `inboundPeers[]` and are written into your local htpasswd files.
2. **Outbound remote credentials** live inside each `outboundRemotes[]` URI and are used by Backrest when it talks to a friend's endpoint.

That means you no longer need to reuse one shared password variable for both directions. For each friend:

- you create and share the inbound credentials they should use against your stack
- they create and share the inbound credentials you should embed in your outbound URIs to reach theirs

The username inside each outbound `backupUri` or `maintenanceUri` must exactly match the remote site's `inboundPeers[].backup.user` or `maintenance.user` value for your instance id. Only the password travels through `.env`; the username lives in `config/site.json`.

If either side uses the wrong pair, backups fail with HTTP authentication errors even when Tailscale connectivity is healthy.

## Site file model

`config/site.json` is the structured description of what Backrest should do for this TailSafe instance. The configurator reads it once at startup and writes generated files under `${BACKREST_DATA_ROOT}/generated`.

| Field | Role |
| --- | --- |
| `instance` | Local TailSafe instance name. Used to identify this site in generated configuration. |
| `outboundRemotes[]` | Each remote TailSafe stack this site sends backups to. Every entry defines an `id`, an endpoint hostname for human reference, explicit backup and maintenance `rest:http://...` URIs, a repository password reference, per-remote maintenance Healthchecks.io URLs, and optional schedule/retention overrides. |
| `inboundPeers[]` | Each remote friend/tailnet allowed to send backups into this site. Every entry defines an `id`, friend-issued endpoint auth key, endpoint hostname, backup and maintenance HTTP credentials, and a `repositorySubdir` under `${REPO_DATA_ROOT}`. |
| `defaults.backupCron` | Default backup schedule (cron expression). |
| `defaults.checkCron` | Default schedule for repository `check` jobs. |
| `defaults.forgetCron` | Default schedule for retention `forget` jobs. |
| `defaults.pruneCron` | Default schedule for `prune` jobs after forget. |
| `defaults.retention` | Default retention counts (`daily`, `weekly`, `monthly`, `yearly`) applied during forget. |
| `sources[]` | Mounted folder sources to back up. Each source has an `id`, one or more `paths` (typically under `/userdata`), optional `excludes`, one or more `destinationIds[]`, and optional per-source Healthchecks.io backup URLs. |

Environment placeholders such as `${TAILSAFE_REMOTE_BACKUP_HTTP_PASSWORD_FRIEND_B}` and `${RESTIC_REPOSITORY_PASSWORD}` in the site file are expanded by the configurator from the full `.env` at generation time. Values inserted into repository URIs are URL-encoded so passwords containing reserved characters (for example `@`, `:`, or `/`) produce valid `rest:http://...` addresses. Repository passwords and htpasswd material are expanded without URL encoding.

For `backupUri` and `maintenanceUri`, the URI path segment should match the identifier the receiving site uses for the sending site. In the one-friend examples (`config/site.one-friend.example.json` and [Agent-assisted install](agent-install.md)), home-a pushes to `/home-a` on friend-b's endpoint, and friend-b pushes to `/friend-b` on home-a's endpoint.

### Legacy migration

The old single-remote schema is still accepted during the migration window:

- `remote` is treated as a one-entry `outboundRemotes[]`
- top-level `healthchecks` become that remote's maintenance hooks
- sources without `destinationIds[]` default to the single outbound remote
- inbound runtime generation falls back to one endpoint trio that uses the legacy `TS_ENDPOINT_*` and `TAILSAFE_*HTTP_*` variables

New deployments should use `outboundRemotes[]` and `inboundPeers[]` directly.

### Preflight checks

Before each backup snapshot, Backrest runs `preflight.sh` as a hook. The current script verifies:

- each configured source path exists on the local filesystem, and
- `RESTIC_REPOSITORY_PASSWORD` is set in the Backrest environment.

It does **not** yet validate outbound Tailscale health or remote endpoint reachability. Connectivity problems surface when restic runs instead. See [Networking](networking.md) for Tailscale startup timing and endpoint prerequisites.

### Regenerating generated assets

The `configurator` service is a **one-shot** job with `restart: "no"`. It runs once, writes files under `${BACKREST_DATA_ROOT}/generated`, and exits. The generated set now includes:

- `backrest-config.json`
- `compose.endpoints.yaml`
- one backup and one maintenance htpasswd file per inbound peer
- one `tailscale-serve-<peer>.json` file per inbound peer (Tailscale Serve TCP forward config for ports `8000` and `8001`)

Restarting Backrest or the generated endpoint services does **not** regenerate those files.

After editing `.env` or `config/site.json`, rerun the configurator explicitly, then start the stack with the generated compose fragment. Use the real absolute host path for your `BACKREST_DATA_ROOT`, for example:

```sh
docker compose --env-file .env -f deploy/compose.yaml up configurator --force-recreate
docker compose --env-file .env \
  -f deploy/compose.yaml \
  -f /volume1/tailsafe/backrest/generated/compose.endpoints.yaml \
  up -d
```

Do not expect a normal `docker compose restart` of the long-lived services alone to pick up configuration changes.

### Outbound runtime (userspace proxy)

On each site, `tailscale-outbound` and `backrest` share a bridge network (`tailsafe-outbound`). The outbound Tailscale container runs userspace Tailscale and exposes an HTTP proxy on port `1055` (`TS_OUTBOUND_HTTP_PROXY_LISTEN`). Backrest reaches remote `rest:http://...` hostnames in `outboundRemotes[]` through `HTTP_PROXY` / `HTTPS_PROXY` pointed at `http://tailscale-outbound:1055`. `NO_PROXY` lists `hc-ping.com` (and local addresses) so Healthchecks pings use the normal internet path and do not go through the Tailscale proxy. Inbound endpoint trios are unchanged: friends still reach your rest-server ports on their peer-specific endpoint hostnames.

### One-sided migration

The namespace-free runtime preserves endpoint hostnames, ports, credentials, and repository URI semantics. One site can migrate independently without requiring friend-side configuration changes.

To upgrade an existing deployment to the namespace-free topology:

1. Update `.env` tags: bump `TAILSAFE_VERSION` to a release that includes the namespace-free configurator and generator changes, and add `TAILSCALE_DOCKER_TAG` (for example `stable`; see `env.example`). Regeneration requires the updated configurator image — older pins will not emit `tailscale-serve-<peer>.json` or the new compose fragment.
2. Refresh your local `deploy/compose.yaml` from `deploy/compose.example.yaml` and merge any site-specific paths or ports.
3. Regenerate runtime assets with the updated configurator so per-peer `tailscale-serve-<peer>.json` files appear under `${BACKREST_DATA_ROOT}/generated`.
4. Recreate the stack with both compose files so the bridge-network and Serve-forward topology is applied.

Friend-side configuration changes are not required as long as your external endpoint hostnames, ports, credentials, and repository URIs stay the same. See [Networking](networking.md#one-sided-migration) for restart behavior after the upgrade.
