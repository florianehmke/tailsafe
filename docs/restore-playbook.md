# Restore Playbook

Use Backrest locally to browse snapshots and restore data from the remote restic repository. Always validate restored content before overwriting live files.

## Restore a normal folder

For standard mounted sources (photos, documents, and similar folders defined under `sources` in `config/site.json`):

1. Open Backrest on the local site (`http://127.0.0.1:9898` with the example port binding).
2. Select the **source plan** that corresponds to the folder you need (match the source `id` from `site.json`).
3. Browse the snapshot tree and pick the snapshot date you want.
4. Restore into a **temporary directory** first—not directly back over the live mount path.
5. Validate ownership, permissions, and file contents in the temporary location.
6. Copy validated files back to the live path only after you are satisfied the restore is complete and correct.

Restoring to a temp directory avoids partial overwrites if the snapshot is wrong, the restore is interrupted, or path mappings differ from what you expected.

## Restore a mounted VolSync repository backup

VolSync repository directories are restic repositories themselves. Treat them as sensitive infrastructure, not ordinary folders.

1. Restore the repository directory from a snapshot into a **temporary path** (for example `/volume1/tailsafe/restore/volsync-prod-verify`).
2. Point restic tooling at the restored copy and confirm it is readable:
   - `restic -r <restored-path> snapshots`
   - `restic -r <restored-path> check` (read-only verification)
3. Use the same `RESTIC_REPOSITORY_PASSWORD` that protects the live repository.
4. Keep the **original live repository untouched** until the restored copy passes verification.
5. Only after verification succeeds, plan a controlled swap or copy back to the live VolSync repository location—and coordinate with any VolSync schedules so nothing writes to the live path during the swap.

If verification fails, discard the temporary restore and try an earlier snapshot before touching production data.

## Maintenance endpoint failure

Maintenance jobs (`check`, `forget`, `prune`) use the maintenance URI on port `8001`, not the append-only backup endpoint on port `8000`. In the multi-site model, each inbound peer has its own maintenance service and its own htpasswd file.

If maintenance actions fail in Backrest or Healthchecks.io reports errors for a specific remote, first identify which peer or remote id is affected, then verify that peer-specific trio:

1. Confirm `rest-server-maintenance-<peer-id>` is running on the endpoint site (`docker compose ps` with the generated compose fragment, or your Synology container UI).
2. Confirm the peer-specific maintenance htpasswd file exists in the generated directory (`rest-server-maint-<peer-id>.htpasswd` under `${BACKREST_DATA_ROOT}/generated`). If htpasswd or other generated files are missing, recreate the configurator service explicitly, wait for it to exit successfully, then restart the stack with the regenerated `compose.endpoints.yaml`.
3. Confirm `tailscale-endpoint-<peer-id>` is connected and reachable from the outbound site.
4. Re-run **`check`** successfully before running **`forget`** or **`prune`**. Do not prune a repository that has not passed a recent check.

Append-only backup traffic for that peer can continue on port `8000` even when maintenance on `8001` is misconfigured, but retention cleanup will not run until maintenance is healthy again.
