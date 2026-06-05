# Setup Guide

This guide explains the one-friend rollout model in detail.
If you are doing a live install, follow [Agent-assisted install](agent-install.md) for the exact order of preparation, file editing, bring-up, and validation.

This guide walks through a first TailSafe rollout between two sites:

- **your side**: the site you are configuring right now
- **friend-b**: one friend site that will exchange backups with you

TailSafe supports multiple friends, but this guide intentionally teaches the **one-friend path first**. After the first exchange works, you can repeat the same pattern for additional friends by adding another outbound remote, another inbound peer, and another set of environment variables.

## Use this guide with

- `README.md` for the repo overview
- `docs/configuration.md` for the full field reference
- `docs/networking.md` for the Tailscale trust model and generated endpoint topology

## Clickable links

- [Tailscale auth keys](https://login.tailscale.com/admin/settings/keys)
- [Healthchecks.io check configuration](https://healthchecks.io/docs/configuring_checks/)
- [Healthchecks.io API](https://healthchecks.io/docs/api/)

## What TailSafe is doing

Each site runs the full TailSafe stack locally.

For a one-friend rollout, each site ends up with:

- one **outbound** Tailscale node on its **own** tailnet
- one **endpoint** Tailscale node on the **other friend's** tailnet
- one `rest-server-backup` service and one `rest-server-maintenance` service behind that endpoint node
- one Backrest instance that pushes local source folders to the remote endpoint

That means each side both **sends** backups out and **receives** backups in, but the credentials for those two directions are different.

## Naming used in this guide

These example names are used throughout the walkthrough:

- your instance id: `home-a`
- your friend id: `friend-b`
- your outbound hostname: `tailsafe-outbound-home-a`
- the hostname your friend will use to reach your endpoint: `tailsafe-home-a-endpoint`
- the hostname you will use to reach your friend's endpoint: `tailsafe-friend-b-endpoint.ts.net`

In `config/site.json`, ids can use hyphens like `friend-b`.

In `.env`, the suffixes are usually uppercase with underscores, so `friend-b` becomes `FRIEND_B`.

Read the variable names literally:

- `TS_ENDPOINT_HOSTNAME_FRIEND_B` on **your** side is the hostname of **your** endpoint that friend-b will use
- `TAILSAFE_REMOTE_*_FRIEND_B` on **your** side means values **friend-b gave you**
- `TAILSAFE_INBOUND_*_FRIEND_B` on **your** side means values **you created for friend-b**

## What each side can prepare without coordination

On your side, you can do all of this before you exchange anything:

1. Clone the repo or copy the published files onto your Synology host.
2. Copy the example files (use the one-friend examples for a first pair; `env.example` and `config/site.example.json` are the multi-friend reference):

   ```bash
   cp deploy/compose.example.yaml deploy/compose.yaml
   cp config/site.one-friend.example.json config/site.json
   cp env.one-friend.example .env
   ```

3. Create the local host directories you want to use for:
   - Backrest data
   - repository storage
   - Tailscale state
   - mounted source folders
4. Decide which folders you want to back up.
5. Decide the local `RESTIC_REPOSITORY_PASSWORD` value you will use for backups you send out.
6. Create your **outbound** Tailscale auth key on the [Tailscale auth keys page](https://login.tailscale.com/admin/settings/keys).
7. Create your Healthchecks checks, or at least decide the names and slugs you want to use.
8. Pick the inbound HTTP users and passwords you want your friend to use when talking to your endpoint.

Friend-b can do the same independently on their side:

1. copy the example files
2. choose host paths
3. choose source folders
4. choose their own `RESTIC_REPOSITORY_PASSWORD`
5. create their own `TS_OUTBOUND_AUTHKEY`
6. create their own Healthchecks checks
7. pick the inbound HTTP users and passwords they will give to you

## What must be exchanged between both sides

Each side needs to send four things to the other side:

1. a Tailscale auth key for the **other side's endpoint node** to join your tailnet
2. the endpoint hostname the other side should target in their outbound URIs
3. the backup HTTP user and password for your endpoint
4. the maintenance HTTP user and password for your endpoint

That means:

- **you send to friend-b** the values they need to back up into **your** endpoint
- **friend-b sends to you** the values you need to back up into **their** endpoint

The username in your outbound `backupUri` or `maintenanceUri` must exactly match the `backup.user` or `maintenance.user` value your friend configured for your site in their `inboundPeers[]` entry.

Important distinction:

- `TS_OUTBOUND_AUTHKEY` is **never** exchanged
- `TS_ENDPOINT_AUTHKEY_<PEER>` **is** exchanged

The auth key you give your friend is for the endpoint node they run on **your** tailnet. It is not the key you use for your own outbound node.

Use this copy-paste exchange checklist when coordinating with friend-b:

```text
I am sending you the values you need to back up into my site:

- endpoint auth key for your endpoint node on my tailnet:
- endpoint hostname you should target:
- backup HTTP user you should use against my endpoint:
- backup HTTP password you should use against my endpoint:
- maintenance HTTP user you should use against my endpoint:
- maintenance HTTP password you should use against my endpoint:
```

```text
I still need these values from you:

- endpoint auth key for my endpoint node on your tailnet:
- endpoint hostname I should target:
- backup HTTP user I should use against your endpoint:
- backup HTTP password I should use against your endpoint:
- maintenance HTTP user I should use against your endpoint:
- maintenance HTTP password I should use against your endpoint:
```

## Healthchecks planning for one friend

For a simple first rollout with one friend and one backup source, create:

- one backup check per source
- three maintenance checks for the remote site:
  - `check`
  - `forget`
  - `prune`

Example names:

- `tailsafe-home-a-photos-backup`
- `tailsafe-home-a-friend-b-check`
- `tailsafe-home-a-friend-b-forget`
- `tailsafe-home-a-friend-b-prune`

Use the [Healthchecks.io check configuration docs](https://healthchecks.io/docs/configuring_checks/) if you want to create them in the UI, or the [Healthchecks.io API](https://healthchecks.io/docs/api/) if you want to script the setup.

## Your side: step-by-step

### 1. Prepare the host paths

Pick real host paths for the values in `.env`. The examples below use Synology-style paths:

- `BACKREST_DATA_ROOT=/volume1/tailsafe/backrest`
- `REPO_DATA_ROOT=/volume1/tailsafe/repos`
- `TAILSAFE_STATE_ROOT=/volume1/tailsafe/state`
- `USERDATA_ROOT=/volume1/tailsafe/userdata`

Because Compose mounts `${USERDATA_ROOT}` to `/userdata` inside the containers, every source path in `config/site.json` should point at `/userdata/...`, not at the host path directly.

For example:

- host folder: `/volume1/tailsafe/userdata/photos`
- container path: `/userdata/photos`

### 2. Create your outbound auth key

Open [Tailscale auth keys](https://login.tailscale.com/admin/settings/keys) on **your** tailnet and create the key that will be used by `tailscale-outbound`.

You will place it in:

- `TS_OUTBOUND_AUTHKEY`

### 3. Create the values you will send to your friend

Choose the values your friend will need to back up into your site:

- endpoint hostname: `tailsafe-home-a-endpoint`
- backup HTTP user: `backup-home-a`
- backup HTTP password: a strong secret
- maintenance HTTP user: `maint-home-a`
- maintenance HTTP password: a strong secret

Also create an auth key on the [Tailscale auth keys page](https://login.tailscale.com/admin/settings/keys) that friend-b will use for their endpoint node on **your** tailnet.

### 4. Receive the values from your friend

Ask friend-b to send you the mirror set for **their** site:

- the auth key for **your** endpoint node on **their** tailnet
- the hostname you should use to reach their endpoint
- their backup HTTP user and password
- their maintenance HTTP user and password

### 5. Fill in your `.env`

Example one-friend `.env`:

```dotenv
TAILSAFE_VERSION=0.2.3
TAILSAFE_IMAGE_NAMESPACE=ghcr.io/pixeljonas/tailsafe
TZ=Europe/Berlin

TS_OUTBOUND_AUTHKEY=tskey-outbound-home-a
TS_OUTBOUND_HOSTNAME=tailsafe-outbound-home-a

TS_ENDPOINT_AUTHKEY_FRIEND_B=tskey-issued-by-friend-b
TS_ENDPOINT_HOSTNAME_FRIEND_B=tailsafe-home-a-endpoint

TAILSAFE_REMOTE_BACKUP_HTTP_PASSWORD_FRIEND_B=friend-b-gave-you-this
TAILSAFE_REMOTE_MAINT_HTTP_PASSWORD_FRIEND_B=friend-b-gave-you-this

TAILSAFE_INBOUND_BACKUP_HTTP_PASSWORD_FRIEND_B=you-created-this-for-friend-b
TAILSAFE_INBOUND_MAINT_HTTP_PASSWORD_FRIEND_B=you-created-this-for-friend-b

RESTIC_REPOSITORY_PASSWORD=home-a-restic-password
BACKREST_BIND_PORT=9898
BACKREST_DATA_ROOT=/volume1/tailsafe/backrest
REPO_DATA_ROOT=/volume1/tailsafe/repos
TAILSAFE_STATE_ROOT=/volume1/tailsafe/state
USERDATA_ROOT=/volume1/tailsafe/userdata
SITE_CONFIG_PATH=../config/site.json
```

How to read this:

- `TS_OUTBOUND_AUTHKEY` belongs to **your** tailnet
- `TS_ENDPOINT_AUTHKEY_FRIEND_B` was issued by **friend-b**
- `TS_ENDPOINT_HOSTNAME_FRIEND_B` is **your** endpoint hostname as seen from friend-b's tailnet
- `TAILSAFE_REMOTE_*_FRIEND_B` came from **friend-b**
- `TAILSAFE_INBOUND_*_FRIEND_B` is what **you** will give to friend-b

### 6. Fill in your `config/site.json`

Example one-friend `config/site.json`:

```json
{
  "instance": "home-a",
  "auth": {
    "disabled": true
  },
  "outboundRemotes": [
    {
      "id": "friend-b",
      "endpointHostname": "tailsafe-friend-b-endpoint.ts.net",
      "backupUri": "rest:http://backup-friend-b:${TAILSAFE_REMOTE_BACKUP_HTTP_PASSWORD_FRIEND_B}@tailsafe-friend-b-endpoint.ts.net:8000/home-a",
      "maintenanceUri": "rest:http://maint-friend-b:${TAILSAFE_REMOTE_MAINT_HTTP_PASSWORD_FRIEND_B}@tailsafe-friend-b-endpoint.ts.net:8001/home-a",
      "repositoryPassword": "${RESTIC_REPOSITORY_PASSWORD}",
      "healthchecks": {
        "check": "https://hc-ping.com/home-a-friend-b-check-uuid",
        "forget": "https://hc-ping.com/home-a-friend-b-forget-uuid",
        "prune": "https://hc-ping.com/home-a-friend-b-prune-uuid"
      }
    }
  ],
  "inboundPeers": [
    {
      "id": "friend-b",
      "endpointAuthKey": "${TS_ENDPOINT_AUTHKEY_FRIEND_B}",
      "endpointHostname": "${TS_ENDPOINT_HOSTNAME_FRIEND_B}",
      "repositorySubdir": "friend-b",
      "backup": {
        "user": "backup-home-a",
        "password": "${TAILSAFE_INBOUND_BACKUP_HTTP_PASSWORD_FRIEND_B}"
      },
      "maintenance": {
        "user": "maint-home-a",
        "password": "${TAILSAFE_INBOUND_MAINT_HTTP_PASSWORD_FRIEND_B}"
      }
    }
  ],
  "defaults": {
    "backupCron": "15 2 * * *",
    "checkCron": "20 3 * * 0",
    "forgetCron": "35 3 * * 0",
    "pruneCron": "50 3 * * 0",
    "retention": {
      "daily": 30,
      "weekly": 8,
      "monthly": 12,
      "yearly": 2
    }
  },
  "sources": [
    {
      "id": "photos",
      "paths": [
        "/userdata/photos"
      ],
      "excludes": [
        "**/.DS_Store"
      ],
      "destinationIds": [
        "friend-b"
      ],
      "healthchecks": {
        "backup": "https://hc-ping.com/home-a-photos-backup-uuid"
      }
    }
  ]
}
```

What to customize:

- `instance`
- the remote endpoint hostname
- the URI path segment so it matches the identifier your friend uses for **your** data
- the Healthchecks URLs
- the `sources[]` list
- any schedules or retention settings

Path rule:

- when **you** push to friend-b, the URI path should match the identifier friend-b uses for **you**
- in this example, friend-b knows your incoming repository as `home-a`, so your outbound URIs end in `/home-a`
- in the opposite direction, friend-b will push to `/friend-b` on your side

### 7. Generate the runtime files

Run the one-shot configurator first:

```bash
docker compose --env-file .env -f deploy/compose.yaml up configurator --force-recreate
```

After it exits successfully, confirm that `${BACKREST_DATA_ROOT}/generated` contains:

- `backrest-config.json`
- `compose.endpoints.yaml`
- `rest-server-backup-friend-b.htpasswd`
- `rest-server-maint-friend-b.htpasswd`

### 8. Start the full stack

Use the real absolute host path from your `.env` for the generated compose fragment. With the example path above:

```bash
docker compose --env-file .env \
  -f deploy/compose.yaml \
  -f /volume1/tailsafe/backrest/generated/compose.endpoints.yaml \
  up -d
```

If your `BACKREST_DATA_ROOT` is different, replace `/volume1/tailsafe/backrest` with your actual value.

### 9. Verify your side

Check all of these before asking friend-b to test:

1. `tailscale-outbound` is running.
2. `tailscale-endpoint-friend-b` is running.
3. `rest-server-backup-friend-b` and `rest-server-maintenance-friend-b` are running.
4. Backrest opens at `http://127.0.0.1:9898`.
5. The generated files exist under `${BACKREST_DATA_ROOT}/generated`.
6. The source folders really exist under `${USERDATA_ROOT}` on the host.
7. Tailscale has had enough time to connect before the first manual or scheduled backup.

## Friend side: step-by-step

Friend-b should follow the same rollout on their side. The important part is that they mirror the relationship, not your exact suffixes or ids.

### 1. Prepare the host paths

Friend-b should choose their own values for:

- `BACKREST_DATA_ROOT`
- `REPO_DATA_ROOT`
- `TAILSAFE_STATE_ROOT`
- `USERDATA_ROOT`

Their source folders should also live under `${USERDATA_ROOT}` and be referenced in their `config/site.json` as `/userdata/...`.

### 2. Create their outbound auth key

Friend-b opens [Tailscale auth keys](https://login.tailscale.com/admin/settings/keys) on **their** tailnet and creates the auth key for:

- `TS_OUTBOUND_AUTHKEY`

### 3. Create the values they will send to you

Friend-b creates:

- an endpoint auth key for **your** endpoint node on friend-b's tailnet
- the endpoint hostname you should target
- the backup HTTP user and password you should use against friend-b's endpoint
- the maintenance HTTP user and password you should use against friend-b's endpoint

### 4. Receive your values

Friend-b receives from you:

- the endpoint auth key for their endpoint node on your tailnet
- the hostname they should use to reach your endpoint
- your backup HTTP user and password
- your maintenance HTTP user and password

### 5. Fill in friend-b's `.env`

Example friend-side `.env`:

```dotenv
TAILSAFE_VERSION=0.2.3
TAILSAFE_IMAGE_NAMESPACE=ghcr.io/pixeljonas/tailsafe
TZ=Europe/Berlin

TS_OUTBOUND_AUTHKEY=tskey-outbound-friend-b
TS_OUTBOUND_HOSTNAME=tailsafe-outbound-friend-b

TS_ENDPOINT_AUTHKEY_HOME_A=tskey-issued-by-home-a
TS_ENDPOINT_HOSTNAME_HOME_A=tailsafe-friend-b-endpoint

TAILSAFE_REMOTE_BACKUP_HTTP_PASSWORD_HOME_A=home-a-gave-you-this
TAILSAFE_REMOTE_MAINT_HTTP_PASSWORD_HOME_A=home-a-gave-you-this

TAILSAFE_INBOUND_BACKUP_HTTP_PASSWORD_HOME_A=friend-b-created-this-for-home-a
TAILSAFE_INBOUND_MAINT_HTTP_PASSWORD_HOME_A=friend-b-created-this-for-home-a

RESTIC_REPOSITORY_PASSWORD=friend-b-restic-password
BACKREST_BIND_PORT=9898
BACKREST_DATA_ROOT=/volume1/tailsafe/backrest
REPO_DATA_ROOT=/volume1/tailsafe/repos
TAILSAFE_STATE_ROOT=/volume1/tailsafe/state
USERDATA_ROOT=/volume1/tailsafe/userdata
SITE_CONFIG_PATH=../config/site.json
```

How friend-b should read this:

- `TS_OUTBOUND_AUTHKEY` belongs to friend-b's tailnet
- `TS_ENDPOINT_AUTHKEY_HOME_A` was issued by **you**
- `TS_ENDPOINT_HOSTNAME_HOME_A` is **friend-b's** endpoint hostname as seen from your tailnet
- `TAILSAFE_REMOTE_*_HOME_A` came from **you**
- `TAILSAFE_INBOUND_*_HOME_A` is what friend-b will give to you

### 6. Fill in friend-b's `config/site.json`

Example friend-side `config/site.json`:

```json
{
  "instance": "friend-b",
  "auth": {
    "disabled": true
  },
  "outboundRemotes": [
    {
      "id": "home-a",
      "endpointHostname": "tailsafe-home-a-endpoint.ts.net",
      "backupUri": "rest:http://backup-home-a:${TAILSAFE_REMOTE_BACKUP_HTTP_PASSWORD_HOME_A}@tailsafe-home-a-endpoint.ts.net:8000/friend-b",
      "maintenanceUri": "rest:http://maint-home-a:${TAILSAFE_REMOTE_MAINT_HTTP_PASSWORD_HOME_A}@tailsafe-home-a-endpoint.ts.net:8001/friend-b",
      "repositoryPassword": "${RESTIC_REPOSITORY_PASSWORD}",
      "healthchecks": {
        "check": "https://hc-ping.com/friend-b-home-a-check-uuid",
        "forget": "https://hc-ping.com/friend-b-home-a-forget-uuid",
        "prune": "https://hc-ping.com/friend-b-home-a-prune-uuid"
      }
    }
  ],
  "inboundPeers": [
    {
      "id": "home-a",
      "endpointAuthKey": "${TS_ENDPOINT_AUTHKEY_HOME_A}",
      "endpointHostname": "${TS_ENDPOINT_HOSTNAME_HOME_A}",
      "repositorySubdir": "home-a",
      "backup": {
        "user": "backup-friend-b",
        "password": "${TAILSAFE_INBOUND_BACKUP_HTTP_PASSWORD_HOME_A}"
      },
      "maintenance": {
        "user": "maint-friend-b",
        "password": "${TAILSAFE_INBOUND_MAINT_HTTP_PASSWORD_HOME_A}"
      }
    }
  ],
  "defaults": {
    "backupCron": "15 2 * * *",
    "checkCron": "20 3 * * 0",
    "forgetCron": "35 3 * * 0",
    "pruneCron": "50 3 * * 0",
    "retention": {
      "daily": 30,
      "weekly": 8,
      "monthly": 12,
      "yearly": 2
    }
  },
  "sources": [
    {
      "id": "documents",
      "paths": [
        "/userdata/documents"
      ],
      "excludes": [],
      "destinationIds": [
        "home-a"
      ],
      "healthchecks": {
        "backup": "https://hc-ping.com/friend-b-documents-backup-uuid"
      }
    }
  ]
}
```

### 7. Generate friend-b's runtime files

Friend-b runs:

```bash
docker compose --env-file .env -f deploy/compose.yaml up configurator --force-recreate
```

After it exits successfully, friend-b should confirm that their generated directory contains:

- `backrest-config.json`
- `compose.endpoints.yaml`
- `rest-server-backup-home-a.htpasswd`
- `rest-server-maint-home-a.htpasswd`

### 8. Start friend-b's full stack

Friend-b then starts the long-lived services with their real generated compose fragment path:

```bash
docker compose --env-file .env \
  -f deploy/compose.yaml \
  -f /volume1/tailsafe/backrest/generated/compose.endpoints.yaml \
  up -d
```

### 9. Verify friend-b's side

Friend-b should verify:

1. `tailscale-outbound` is running.
2. `tailscale-endpoint-home-a` is running.
3. `rest-server-backup-home-a` and `rest-server-maintenance-home-a` are running.
4. Backrest opens locally.
5. Their generated files exist.
6. Their source folders exist under their `${USERDATA_ROOT}`.

## First end-to-end test

Once both sides are up:

1. Wait until the outbound and endpoint Tailscale nodes show as connected.
2. Trigger one manual backup from your Backrest UI.
3. Confirm the backup plan reaches the remote endpoint successfully.
4. Confirm maintenance checks can run against port `8001`.
5. Ask friend-b to do the same in the opposite direction.

If one direction works and the other does not, compare the exchanged values again:

- endpoint auth key
- endpoint hostname
- backup user and password
- maintenance user and password

Most first-run failures come from those four values not being mirrored correctly.

## Adding a second friend later

After the one-friend rollout works, add another friend by repeating the same pattern:

1. add `TS_ENDPOINT_AUTHKEY_<NEW_PEER>` and `TS_ENDPOINT_HOSTNAME_<NEW_PEER>` to `.env`
2. add `TAILSAFE_REMOTE_*_<NEW_PEER>` and `TAILSAFE_INBOUND_*_<NEW_PEER>` to `.env`
3. add one more object to `outboundRemotes[]`
4. add one more object to `inboundPeers[]`
5. add the new friend id to any relevant `sources[].destinationIds[]`
6. rerun the configurator
7. restart the stack with the regenerated `compose.endpoints.yaml`

Once you have more than one inbound peer, use peer-suffixed endpoint hostnames and inbound usernames as shown in `env.example` and `config/site.example.json` (for example `tailsafe-home-a-endpoint-friend-b` and `backup-home-a-friend-b`) so each friend keeps a distinct listener identity.

## Agent checklist

Use [Agent-assisted install](agent-install.md) as the canonical checklist.
Come back to this guide when you need the detailed rationale, mirrored examples, or the full one-friend narrative.
