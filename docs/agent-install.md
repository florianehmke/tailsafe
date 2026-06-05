# Agent-Assisted Install

Canonical first-install runbook for agents and first-time TailSafe operators. Work through the intake checklist and friend worksheet before editing host files or starting containers.

## Who This Guide Is For

Use this guide when you are:

- deploying TailSafe for the first time with one friend
- helping an operator prepare inputs, coordinate the exchange, and bring up the stack on a Synology or other Docker host
- following a phased rollout instead of rediscovering pitfalls from ad hoc installs

This guide assumes a **one-friend** path first (`home-a` ↔ `friend-b`). After the pair is healthy, repeat the same pattern for additional friends.

For the detailed rationale and mirrored examples on both sides, see [Setup guide](setup-guide.md). For field reference, see [Configuration](configuration.md) and [Networking](networking.md).

## Before You Touch the Host

Complete this intake before SSH, file copies, or `docker compose` commands.

### Local host facts

- Host type (`Synology` or generic Docker host)
- SSH user and access pattern
- Project root on the target host
- Exact `docker compose` command path
- CPU architecture
- Backrest UI exposure (`localhost` only or LAN)
- Real source folders to back up

### Local decisions

- Instance id
- First-friend or additional-peer rollout
- Rollout mode (`inbound-first`, `full two-way`, or `upgrade existing site`)
- Healthchecks strategy
- Naming convention
- Target `TAILSAFE_VERSION`

### Friend exchange data

- Values you will send
- Values you must receive
- Values that stay local only
- Values that belong in secure storage

Do not continue until:

- local host facts are complete
- you know whether this is a new install or an upgrade
- you know which rollout mode you are following
- the friend exchange values required for your chosen rollout mode are available (see Phase 3)

## Phase 0: Understand the Rollout

Each site runs the full TailSafe stack locally:

- one **outbound** Tailscale node on its **own** tailnet (Backrest pushes backups out through this node)
- one **endpoint** Tailscale node per inbound friend on **that friend's** tailnet (receives their backups in)
- generated `rest-server-backup` and `rest-server-maintenance` services behind each endpoint node

Credentials for the two directions are different. Outbound and inbound HTTP passwords are coordinated independently — do not mix them.

Example naming used in this guide:

- your instance id: `home-a`
- your friend id: `friend-b`
- your outbound hostname: `tailsafe-outbound-home-a`
- hostname your friend targets on your site: `tailsafe-home-a-endpoint`
- hostname you target on friend's site: `tailsafe-friend-b-endpoint.ts.net`

## Phase 1: Collect Local Host Facts

Gather everything under **Local host facts** and **Local decisions** from the intake checklist.

On your side, you can prepare most of this before any friend exchange:

1. Confirm host type, SSH access, project root, and `docker compose` path.
2. Choose real host paths for Backrest data, repos, Tailscale state, and userdata mounts (Synology example: `/volume1/tailsafe/...`).
3. List source folders to back up; paths in `config/site.json` will use `/userdata/...` inside containers.
4. Create your **outbound** Tailscale auth key on your tailnet — this stays local (`TS_OUTBOUND_AUTHKEY`).
5. Decide instance id, Healthchecks check names, and target `TAILSAFE_VERSION`.
6. Choose inbound HTTP users and passwords you will share with your friend.

## Phase 2: Collect Friend Exchange Data

Use the friend worksheet below when coordinating with your friend. For `full two-way`, complete both **Send to friend** and **Receive from friend** before editing `.env` or `config/site.json`. For `inbound-first`, you can defer the outbound remote values in **Receive from friend** until after inbound bring-up (see Phase 3).

### Send to friend

- endpoint auth key for their endpoint node on your tailnet
- endpoint hostname / FQDN they should target
- backup HTTP user and password
- maintenance HTTP user and password

### Receive from friend

- endpoint auth key for your endpoint node on their tailnet
- endpoint hostname / FQDN you should target
- backup HTTP user and password
- maintenance HTTP user and password

### Never exchange

- `TS_OUTBOUND_AUTHKEY`

### Store securely

- every Tailscale auth key
- all HTTP passwords
- `RESTIC_REPOSITORY_PASSWORD`
- any Backrest UI credential if LAN exposure is enabled

The auth key you give your friend is for the endpoint node they run on **your** tailnet. It is not the key you use for your own outbound node.

## Phase 3: Choose the Rollout Mode

Pick one branch and follow it through file preparation and bring-up:

- `inbound-first`: stand up the receiving side first so your friend can test pushes into your site
- `full two-way`: configure inbound and outbound together once both sides have exchanged all required values
- `upgrade existing site`: stop and switch to the upgrade branch before editing greenfield examples

Minimum exchange values by mode:

- `inbound-first`: complete **Send to friend** and the inbound items in **Receive from friend** (endpoint auth key for your endpoint node on their tailnet). Defer their remote hostname and remote HTTP passwords until you are ready to configure outbound remotes.
- `full two-way`: complete the full **Receive from friend** worksheet before editing outbound remote URIs.
- `upgrade existing site`: compare your live `deploy/compose.yaml` with `deploy/compose.example.yaml` and follow the upgrade path in [Configuration](configuration.md) instead of copying greenfield examples blindly.

## Phase 4: Prepare the Local Files

```bash
mkdir -p /volume1/tailsafe/backrest /volume1/tailsafe/repos /volume1/tailsafe/state /volume1/tailsafe/userdata
cp deploy/compose.example.yaml deploy/compose.yaml
cp env.one-friend.example .env
cp config/site.one-friend.example.json config/site.json
```

Edit `.env` and `config/site.json` only after the intake and friend worksheet are complete.

For `inbound-first`, you may keep placeholder outbound remote values in `.env` and `outboundRemotes[]` until friend-b supplies their remote hostname and HTTP passwords. Inbound bring-up only requires the exchanged inbound values from Phase 3.

Run the commands below from your project root on the target host.

## Phase 5: Generate Runtime Assets and Start the Stack

```bash
docker compose --env-file .env -f deploy/compose.yaml up configurator --force-recreate
docker compose --env-file .env \
  -f deploy/compose.yaml \
  -f /volume1/tailsafe/backrest/generated/compose.endpoints.yaml \
  up -d
```

After the configurator exits successfully, confirm `${BACKREST_DATA_ROOT}/generated` contains `backrest-config.json`, `compose.endpoints.yaml`, and the peer htpasswd files before running the second command. Do not start the long-lived stack without the generated fragment.

The second command must use the real absolute `BACKREST_DATA_ROOT` path from `.env`, not the Synology example path if your host paths differ.

- If your sources already fit under one `USERDATA_ROOT`, use the example unchanged.
- If your Synology sources live in separate host locations, replace the single `${USERDATA_ROOT}:/userdata:ro` bind with explicit bind mounts in `deploy/compose.yaml` and keep the `config/site.json` paths under `/userdata/...`.
- If you expose Backrest beyond localhost, replace the example `auth.disabled: true` block with an enabled Backrest auth user before calling the install complete.

## Phase 6: Validate Pair Health

1. Config generated successfully
2. Base stack is up
3. Generated endpoint services are up
4. Tailscale nodes are online in the correct tailnets
5. Remote HTTP endpoints return the expected auth challenge
6. First manual backup succeeds
7. Maintenance path succeeds
8. Backrest UI access is confirmed if the UI is exposed

For `inbound-first`, treat steps 5–7 as deferred until outbound remotes are configured with real friend-b values.

| Signal | Meaning |
| --- | --- |
| `401` on `:8000` / `:8001` | healthy auth challenge, endpoint listener reachable |
| `502 Bad Gateway` | request reached a proxy layer, but the backend path is broken |
| timeout / host unreachable | Tailscale routing, DNS, ACL, or node state is still broken |

## Phase 7: Troubleshoot by Symptom

Use these entries when validation fails. Start from the symptom you see in logs, probes, or the Backrest UI.

### `invalid key`

- Usually means: Tailscale rejected the auth key during `tailscale up`
- Likely causes: outbound key used for an endpoint node (or the reverse), key issued by the wrong tailnet admin, expired or revoked key, pasted value with extra whitespace
- Check next: confirm `TS_OUTBOUND_AUTHKEY` comes from your tailnet and `TS_ENDPOINT_AUTHKEY_FRIEND_B` comes from friend-b's tailnet; inspect `tailscale-outbound` and `tailscale-endpoint-friend-b` logs
- Healthy signal: both nodes show online in the correct tailnet admin consoles

### `host is unreachable`

- Usually means: the outbound site cannot open a transport path to the remote endpoint hostname
- Likely causes: endpoint node offline, ACL blocking ports `8000` and `8001`, wrong hostname in `outboundRemotes[]`, MagicDNS not resolving the `.ts.net` name yet
- Check next: Tailscale admin on both tailnets, ACL rules for both directions, hostname in backup/maintenance URIs vs the peer's actual endpoint FQDN
- Healthy signal: probe returns `401` on `:8000` / `:8001` from the outbound site

### `502 Bad Gateway`

- Usually means: the request reached a proxy layer, but the rest-server backend is not attached cleanly
- Likely causes: stale sidecars after endpoint recreate, backend service not sharing the expected namespace
- Check next: endpoint container state, rest-server recreation for the affected peer, fresh `401` probe after restart
- Healthy signal: `401` on the same port after recreation

### `401` vs `200` vs timeout on `:8000` / `:8001`

- Usually means: the probe reached different layers depending on which response you got
- Likely causes: `401` without credentials is the expected auth challenge; `200` without credentials suggests a miswired backend or wrong listener; timeout means routing, DNS, ACL, or node state is still broken
- Check next: probe both ports through the outbound userspace proxy (for example from the `tailscale-outbound` container where `HTTP_PROXY` is set, or via a manual Backrest backup attempt); compare backup (`8000`) and maintenance (`8001`) results. A host-shell `curl` without that proxy does not follow the outbound path
- Healthy signal: `401` on both ports when probed without credentials

### `context deadline exceeded`

- Usually means: Backrest or restic timed out waiting for the remote endpoint to respond
- Likely causes: Tailscale node not fully connected yet after cold start, outbound proxy not ready, wrong `rest:http://...` URI, first connection still warming up
- Check next: confirm both Tailscale nodes are connected, wait and retry a manual backup, verify `outboundRemotes[]` URIs and exchanged HTTP credentials
- Healthy signal: manual backup completes without deadline errors once nodes are online

### Backrest crash-loop

- Usually means: the Backrest container exits and Compose keeps restarting it
- Likely causes: invalid or missing generated `backrest-config.json`, configurator never completed successfully, volume permission problems under `${BACKREST_DATA_ROOT}`, image architecture mismatch
- Check next: `docker compose logs backrest`, confirm `${BACKREST_DATA_ROOT}/generated/` exists after configurator exit, rerun configurator if generated files are missing
- Healthy signal: Backrest stays running and the UI loads on loopback

### UI password unknown

- Usually means: the operator cannot log into the Backrest UI after auth was enabled or changed
- Likely causes: password was never recorded in secure storage, `auth.disabled` was toggled without documenting credentials, wrong password format assumed (Backrest uses its own hash format, not a raw Apache htpasswd bcrypt string)
- Check next: follow Backrest's password-reset flow for the UI auth user; confirm `auth.disabled` in `config/site.json` matches your exposure model (see [Networking](networking.md#ui-exposure))
- Healthy signal: documented credentials work at `http://127.0.0.1:${BACKREST_BIND_PORT}` (or your chosen bind port)

### ARM Mac / Podman image mismatch

- Usually means: the pulled container image does not match the host CPU architecture
- Likely causes: amd64-only images on an arm64 Mac without emulation, Podman platform defaults differing from Docker, stale cached image for the wrong arch
- Check next: `uname -m` on the host, inspect image manifest or pull logs for platform warnings, set an explicit `--platform` if your runtime supports it
- Healthy signal: all TailSafe containers start without `exec format error` or platform mismatch messages

## Next References

- [Setup guide](setup-guide.md) — detailed one-friend narrative and mirrored your-side / friend-side walkthrough
- [Configuration](configuration.md) — `.env` vs `site.json`, secrets, and regeneration lifecycle
- [Networking](networking.md) — Tailscale roles, endpoint trios, and connectivity expectations
- [Restore playbook](restore-playbook.md) — folder restores and maintenance troubleshooting
