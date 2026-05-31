# Configuration

TailSafe separates published examples from the files you actually run at each site. Copy the example files, fill in secrets locally, and keep production copies out of version control.

## User-owned files

These three files define how a live TailSafe deployment behaves. They are not committed by the project; you create and maintain them on each Synology (or other host).

### `deploy/compose.yaml`

Your site-local Compose file. Start from `deploy/compose.example.yaml` and adjust image tags, volume paths, and hostname values for your environment. This file wires together the configurator, Tailscale containers, Backrest, and the two rest-server instances.

### `.env`

Environment variables consumed by Compose and passed into the configurator. Start from `env.example`. It holds Tailscale auth keys, HTTP credentials for the rest-server endpoints, the restic repository password, filesystem paths (`BACKREST_DATA_ROOT`, `REPO_DATA_ROOT`, `USERDATA_ROOT`, and related roots), and the path to your site file (`SITE_CONFIG_PATH`).

### `config/site.json`

The site configuration consumed by the configurator to generate `backrest-config.json`, htpasswd files, and related runtime material. Start from `config/site.example.json`. Each site keeps its own copy with friend-specific URIs, schedules, sources, and Healthchecks.io URLs.

## Required secrets

Set these in `.env` before starting the stack. Never commit real values to the repository.

Each site runs the **full** TailSafe stack locally, including both Tailscale roles and both rest-server containers. That means **both** `TS_OUTBOUND_AUTHKEY` and `TS_ENDPOINT_AUTHKEY` belong in **each** site's local `.env`—not split across friends.

Auth keys come from different tailnet admins even though every site runs the same stack:

| Variable | Purpose |
| --- | --- |
| `TS_OUTBOUND_AUTHKEY` | Issue this for **this site's own tailnet**. Used by `tailscale-outbound` so Backrest can push backups to the remote friend's endpoint over Tailscale. |
| `TS_ENDPOINT_AUTHKEY` | Issue this from **your friend** so `tailscale-endpoint` can join **their tailnet** and receive their backup and maintenance traffic. |
| `TAILSAFE_BACKUP_HTTP_PASSWORD` | Password for the append-only backup rest-server user (`backup` by default). Embedded in the backup repository URI in `site.json`. |
| `TAILSAFE_MAINT_HTTP_PASSWORD` | Password for the maintenance rest-server user (`maint` by default). Embedded in the maintenance repository URI in `site.json`. |
| `RESTIC_REPOSITORY_PASSWORD` | Encryption password for the restic repository. Referenced in `site.json` and required by Backrest and restic tooling. |

Related non-secret variables must also be set:

| Variable | Purpose |
| --- | --- |
| `TS_OUTBOUND_HOSTNAME` | Tailscale hostname registered by this site's outbound node (for example `tailsafe-outbound`). |
| `TS_ENDPOINT_HOSTNAME` | Tailscale hostname registered by this site's endpoint node (for example `tailsafe-endpoint`). Your friend targets this hostname in their `site.json` URIs. |
| `TAILSAFE_BACKUP_HTTP_USER` / `TAILSAFE_MAINT_HTTP_USER` | HTTP users for the two rest-server instances (defaults: `backup`, `maint`). |
| `TAILSAFE_IMAGE_NAMESPACE` / `TAILSAFE_VERSION` | GHCR image namespace and pinned tag used by `deploy/compose.yaml` (see `env.example`). |
| Path roots (`BACKREST_DATA_ROOT`, `REPO_DATA_ROOT`, `USERDATA_ROOT`, and related) | Filesystem locations for generated assets, repository storage, userdata mounts, and Tailscale state. |

The five secret variables above are the credentials that protect cross-site backup access and repository data.

## HTTP credential coordination

The same backup and maintenance HTTP credential pairs in `.env` are used for **both**:

1. **Local inbound auth** — the configurator writes htpasswd files for your local `rest-server-backup` and `rest-server-maintenance` containers from `TAILSAFE_BACKUP_HTTP_*` and `TAILSAFE_MAINT_HTTP_*`.
2. **Remote outbound auth** — the configurator expands those same placeholders into the `rest:http://...` URIs in `site.json` that Backrest uses to authenticate to your friend's endpoint.

Both friends must coordinate and agree on the shared backup credential pair and shared maintenance credential pair. Your outbound URI passwords must match what your friend configured for their inbound rest-server htpasswd files (and vice versa). If the pairs diverge, backups fail with HTTP authentication errors even when Tailscale connectivity is healthy.

## Site file model

`config/site.json` is the single structured description of what Backrest should do for this TailSafe instance. The configurator reads it once at startup and writes generated files under `${BACKREST_DATA_ROOT}/generated`.

| Field | Role |
| --- | --- |
| `instance` | Local TailSafe instance name. Used to identify this site in generated configuration. |
| `remote.id` | Identifier for the remote friend (also used as the repository path segment in rest-server URLs). |
| `remote.backupUri` | Plain `rest:http://...` URI for append-only backups over Tailscale (port `8000` on the friend's endpoint hostname). |
| `remote.maintenanceUri` | Plain `rest:http://...` URI for maintenance operations over Tailscale (port `8001`). |
| `remote.repositoryPassword` | Reference to `${RESTIC_REPOSITORY_PASSWORD}` for restic encryption. |
| `defaults.backupCron` | Daily backup schedule (cron expression). |
| `defaults.checkCron` | Schedule for repository `check` jobs. |
| `defaults.forgetCron` | Schedule for retention `forget` jobs. |
| `defaults.pruneCron` | Schedule for `prune` jobs after forget. |
| `defaults.retention` | Retention counts (`daily`, `weekly`, `monthly`, `yearly`) applied during forget. |
| `sources[]` | Mounted folder sources to back up. Each source has an `id`, one or more `paths` (typically under `/userdata`), optional `excludes`, and optional per-source Healthchecks.io URLs. |
| `healthchecks` | Top-level Healthchecks.io webhook URLs for repository maintenance actions (`check`, `forget`, `prune`). |

Environment placeholders such as `${TAILSAFE_BACKUP_HTTP_PASSWORD}` and `${RESTIC_REPOSITORY_PASSWORD}` in the site file are expanded by the configurator from `.env` at generation time. Values inserted into repository URIs are URL-encoded so passwords containing reserved characters (for example `@`, `:`, or `/`) produce valid `rest:http://...` addresses. The repository password field itself is expanded without URL encoding.

### Preflight checks

Before each backup snapshot, Backrest runs `preflight.sh` as a hook. The current script verifies:

- each configured source path exists on the local filesystem, and
- `RESTIC_REPOSITORY_PASSWORD` is set in the Backrest environment.

It does **not** yet validate outbound Tailscale health or remote endpoint reachability. Connectivity problems surface when restic runs instead. See [Networking](networking.md) for Tailscale startup timing and endpoint prerequisites.

### Regenerating generated assets

The `configurator` service is a **one-shot** job with `restart: "no"`. It runs once, writes files under `${BACKREST_DATA_ROOT}/generated` (including `backrest-config.json` and htpasswd files), and exits. Restarting Backrest or the rest-server containers does **not** regenerate those files.

After editing `.env` or `config/site.json`, recreate or rerun the configurator explicitly, for example:

```sh
docker compose up configurator --force-recreate
```

Wait for the configurator container to exit successfully, then restart dependent services if they are already running. Do not expect a normal `docker compose restart` of the long-lived services alone to pick up configuration changes.
