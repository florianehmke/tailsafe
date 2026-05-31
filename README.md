# TailSafe

TailSafe is a container-based friend-to-friend offsite backup project for Synology systems.

## What it ships

- GHCR-hosted runtime images
- an example Compose deployment
- a generator for Backrest `backrest-config.json`
- helper scripts for local preflight checks (source paths and required secrets) and REST auth material
- operator docs for setup, restore, and troubleshooting

## What it does not ship

- live deployment to your Synology
- committed site secrets
- committed production Compose files

## Prerequisites

`mise run ci` requires [mise](https://mise.jdx.dev/) and Docker with Compose support.

## Quickstart

1. Copy the example deployment files to site-local paths:

   ```bash
   cp deploy/compose.example.yaml deploy/compose.yaml
   cp config/site.example.json config/site.json
   cp env.example .env
   ```

2. Edit `.env` and set your Tailscale auth keys (`TS_OUTBOUND_AUTHKEY` for your own tailnet, `TS_ENDPOINT_AUTHKEY` from your friend), Backrest HTTP credentials (`TAILSAFE_BACKUP_HTTP_USER`, `TAILSAFE_BACKUP_HTTP_PASSWORD`, `TAILSAFE_MAINT_HTTP_USER`, `TAILSAFE_MAINT_HTTP_PASSWORD`), the Restic repository password (`RESTIC_REPOSITORY_PASSWORD`), the GHCR image namespace (`TAILSAFE_IMAGE_NAMESPACE`), and a pinned image tag (`TAILSAFE_VERSION`). Coordinate the HTTP credential pairs with your friend so your outbound URIs match their inbound rest-server auth — see [Configuration](docs/configuration.md#http-credential-coordination).

3. Start the stack:

   ```bash
   docker compose --env-file .env -f deploy/compose.yaml up -d
   ```

4. Open Backrest at [http://127.0.0.1:9898](http://127.0.0.1:9898).

See [Configuration](docs/configuration.md) for the full `site.json` model and [Deployment ownership](#deployment-ownership) for which files stay on the host.

## Local workflow

Use `mise run ci` to validate the repository.
Use `mise run check:release` as the pre-release validation entrypoint before tagging or publishing images.
Use `deploy/compose.example.yaml` and `config/site.example.json` as the starting point for a site-local deployment.
All CI/CD helper scripts live under `.cicd/scripts/`.

## Documentation

- [Configuration](docs/configuration.md) — user-owned files, required secrets, and the `site.json` model
- [Networking](docs/networking.md) — outbound and endpoint Tailscale roles, rest-server ports, and UI exposure
- [Restore playbook](docs/restore-playbook.md) — folder restores, VolSync repository recovery, and maintenance troubleshooting

## Deployment ownership

TailSafe publishes images and examples. You own the real deployment files used at each site:

- `deploy/compose.yaml` — your site-local Compose stack (copy from `deploy/compose.example.yaml`)
- `.env` — secrets and path configuration (copy from `env.example`)
- `config/site.json` — schedules, sources, remote URIs, and Healthchecks.io URLs (copy from `config/site.example.json`)

Keep production copies on the host or in private storage; do not commit them to this repository.
