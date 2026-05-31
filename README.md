# TailSafe

TailSafe is a container-based friend-to-friend offsite backup project for Synology systems.

## What it ships

- GHCR-hosted runtime images
- an example base Compose deployment plus a generated endpoint fragment
- generators for Backrest `backrest-config.json` and `compose.endpoints.yaml`
- helper scripts for local preflight checks (source paths and required secrets) and REST auth material
- operator docs for setup, restore, and troubleshooting

Only the TailSafe-owned configurator image is UBI-based right now. The Backrest, rest-server, and Tailscale images remain thin wrappers around their upstream images.

## What it does not ship

- live deployment to your Synology
- committed site secrets
- committed production Compose files

## Prerequisites

`mise run ci` requires [mise](https://mise.jdx.dev/) and Docker with Compose support.

If this is your first real deployment with a friend, start with the step-by-step [Setup guide](docs/setup-guide.md) before using the shorter quickstart below.

## Quickstart

1. Copy the example deployment files to site-local paths:

   ```bash
   cp deploy/compose.example.yaml deploy/compose.yaml
   cp config/site.example.json config/site.json
   cp env.example .env
   ```

2. Edit `.env` and `config/site.json`. The new model separates:

   - one global outbound Tailscale auth key (`TS_OUTBOUND_AUTHKEY`) for the Backrest side
   - one endpoint auth key and hostname per inbound friend (`TS_ENDPOINT_AUTHKEY_<PEER>`, `TS_ENDPOINT_HOSTNAME_<PEER>`)
   - one outbound HTTP password pair per remote TailSafe stack (`TAILSAFE_REMOTE_*`)
   - one inbound HTTP password pair per inbound peer (`TAILSAFE_INBOUND_*`)
   - the shared restic encryption password (`RESTIC_REPOSITORY_PASSWORD`)
   - the GHCR image namespace (`TAILSAFE_IMAGE_NAMESPACE`) and pinned image tag (`TAILSAFE_VERSION`)

   See [Configuration](docs/configuration.md) for the full `outboundRemotes[]`, `inboundPeers[]`, and `sources[].destinationIds[]` model, including how inbound and outbound credentials are coordinated independently.

3. Generate the runtime assets:

   ```bash
   docker compose --env-file .env -f deploy/compose.yaml up configurator --force-recreate
   ```

4. Start the long-lived services with the generated endpoint fragment from your real Backrest data path. With the example `BACKREST_DATA_ROOT=/volume1/tailsafe/backrest`, that looks like:

   ```bash
   docker compose --env-file .env \
     -f deploy/compose.yaml \
     -f /volume1/tailsafe/backrest/generated/compose.endpoints.yaml \
     up -d
   ```

5. Open Backrest at [http://127.0.0.1:9898](http://127.0.0.1:9898).

See [Configuration](docs/configuration.md) for the full `site.json` model and [Deployment ownership](#deployment-ownership) for which files stay on the host.

## Local workflow

Use `mise run ci` to validate the repository.
Use `mise run check:release` as the pre-release validation entrypoint before tagging or publishing images.
Use `deploy/compose.example.yaml` and `config/site.example.json` as the starting point for a site-local deployment.
All CI/CD helper scripts live under `.cicd/scripts/`.

## Documentation

- [Setup guide](docs/setup-guide.md) — one-friend-first rollout steps for your side and the friend's side, with example config and agent checklist
- [Configuration](docs/configuration.md) — user-owned files, required secrets, and the `site.json` model
- [Networking](docs/networking.md) — outbound and endpoint Tailscale roles, rest-server ports, and UI exposure
- [Restore playbook](docs/restore-playbook.md) — folder restores, VolSync repository recovery, and maintenance troubleshooting

## Deployment ownership

TailSafe publishes images and examples. You own the real deployment files used at each site:

- `deploy/compose.yaml` — your site-local Compose stack (copy from `deploy/compose.example.yaml`)
- `.env` — secrets and path configuration (copy from `env.example`)
- `config/site.json` — schedules, sources, outbound remotes, inbound peers, and Healthchecks.io URLs (copy from `config/site.example.json`)
- `${BACKREST_DATA_ROOT}/generated/compose.endpoints.yaml` — generated inbound endpoint services for your configured peers

Keep production copies on the host or in private storage; do not commit them to this repository.
