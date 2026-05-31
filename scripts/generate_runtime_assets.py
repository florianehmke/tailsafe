#!/usr/bin/env python3
import json
import os
import sys

from tailsafe_site import (
    backup_htpasswd_path,
    expand_env,
    inbound_peers,
    load_site,
    maintenance_htpasswd_path,
)


def ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def render_compose_fragment(peers: list[dict]) -> str:
    if not peers:
        return "---\nservices: {}\n"

    lines = ["---", "services:"]
    for peer in peers:
        peer_id = peer["id"]
        endpoint_service = f"tailscale-endpoint-{peer_id}"
        backup_service = f"rest-server-backup-{peer_id}"
        maintenance_service = f"rest-server-maintenance-{peer_id}"
        state_root = f"${{TAILSAFE_STATE_ROOT}}/endpoint-{peer_id}"
        repo_root = f"${{REPO_DATA_ROOT}}/{peer['repositorySubdir']}"

        lines.extend(
            [
                f"  {endpoint_service}:",
                "    image: ${TAILSAFE_IMAGE_NAMESPACE}/tailsafe-tailscale:${TAILSAFE_VERSION}",
                "    environment:",
                f"      TS_AUTHKEY: {peer['endpointAuthKey']}",
                f"      TS_HOSTNAME: {peer['endpointHostname']}",
                "      TS_STATE_DIR: /var/lib/tailscale",
                "    volumes:",
                f"      - {state_root}:/var/lib/tailscale",
                "    restart: unless-stopped",
                "",
                f"  {backup_service}:",
                "    image: ${TAILSAFE_IMAGE_NAMESPACE}/tailsafe-rest-server:${TAILSAFE_VERSION}",
                f"    network_mode: service:{endpoint_service}",
                "    depends_on:",
                "      configurator:",
                "        condition: service_completed_successfully",
                f"      {endpoint_service}:",
                "        condition: service_started",
                "    environment:",
                '      OPTIONS: "--listen :8000 --append-only"',
                f"      PASSWORD_FILE: {backup_htpasswd_path(peer_id)}",
                "    volumes:",
                "      - ${BACKREST_DATA_ROOT}/generated:/generated:ro",
                f"      - {repo_root}:/data",
                "    restart: unless-stopped",
                "",
                f"  {maintenance_service}:",
                "    image: ${TAILSAFE_IMAGE_NAMESPACE}/tailsafe-rest-server:${TAILSAFE_VERSION}",
                f"    network_mode: service:{endpoint_service}",
                "    depends_on:",
                "      configurator:",
                "        condition: service_completed_successfully",
                f"      {endpoint_service}:",
                "        condition: service_started",
                "    environment:",
                '      OPTIONS: "--listen :8001"',
                f"      PASSWORD_FILE: {maintenance_htpasswd_path(peer_id)}",
                "    volumes:",
                "      - ${BACKREST_DATA_ROOT}/generated:/generated:ro",
                f"      - {repo_root}:/data",
                "    restart: unless-stopped",
                "",
            ]
        )

    return "\n".join(lines).rstrip() + "\n"


def htpasswd_manifest(peers: list[dict]) -> dict:
    return {
        "peers": [
            {
                "id": peer["id"],
                "backupHtpasswdPath": backup_htpasswd_path(peer["id"]),
                "backupUser": expand_env(peer["backup"]["user"]),
                "backupPassword": expand_env(peer["backup"]["password"]),
                "maintenanceHtpasswdPath": maintenance_htpasswd_path(peer["id"]),
                "maintenanceUser": expand_env(peer["maintenance"]["user"]),
                "maintenancePassword": expand_env(peer["maintenance"]["password"]),
            }
            for peer in peers
        ]
    }


def main(input_path: str, compose_output_path: str, manifest_output_path: str) -> None:
    site = load_site(input_path)
    peers = inbound_peers(site)

    ensure_parent_dir(compose_output_path)
    ensure_parent_dir(manifest_output_path)

    with open(compose_output_path, "w", encoding="utf-8") as handle:
        handle.write(render_compose_fragment(peers))

    with open(manifest_output_path, "w", encoding="utf-8") as handle:
        json.dump(htpasswd_manifest(peers), handle, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: generate_runtime_assets.py <input.json> <compose-output.yaml> <manifest-output.json>"
        )
    main(sys.argv[1], sys.argv[2], sys.argv[3])
