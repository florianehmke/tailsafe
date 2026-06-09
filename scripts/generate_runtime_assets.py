#!/usr/bin/env python3
import json
import os
import sys

from tailsafe_site import (
    backup_htpasswd_path,
    endpoint_network_name,
    expand_env,
    inbound_peers,
    load_site,
    maintenance_htpasswd_path,
    serve_config_path,
)


def ensure_parent_dir(path: str) -> None:
    parent = os.path.dirname(path)
    if parent:
        os.makedirs(parent, exist_ok=True)


def render_serve_config(peer_id: str) -> dict:
    backup_service = f"rest-server-backup-{peer_id}"
    maintenance_service = f"rest-server-maintenance-{peer_id}"
    return {
        "TCP": {
            "8000": {"TCPForward": f"{backup_service}:8000"},
            "8001": {"TCPForward": f"{maintenance_service}:8001"},
        }
    }


def serve_config_output_path(compose_output_path: str, peer_id: str) -> str:
    parent = os.path.dirname(compose_output_path)
    return os.path.join(parent, f"tailscale-serve-{peer_id}.json")


def render_compose_fragment(peers: list[dict]) -> str:
    if not peers:
        return "---\nservices: {}\n"

    lines = ["---", "services:"]
    for peer in peers:
        peer_id = peer["id"]
        endpoint_service = f"tailscale-endpoint-{peer_id}"
        backup_service = f"rest-server-backup-{peer_id}"
        maintenance_service = f"rest-server-maintenance-{peer_id}"
        network_name = endpoint_network_name(peer_id)
        state_root = f"${{TAILSAFE_STATE_ROOT}}/endpoint-{peer_id}"
        repo_root = f"${{REPO_DATA_ROOT}}/{peer['repositorySubdir']}"

        lines.extend(
            [
                f"  {endpoint_service}:",
                "    image: tailscale/tailscale:${TAILSCALE_DOCKER_TAG}",
                "    depends_on:",
                "      configurator:",
                "        condition: service_completed_successfully",
                "    environment:",
                f"      TS_AUTHKEY: {peer['endpointAuthKey']}",
                '      TS_AUTH_ONCE: "true"',
                f"      TS_HOSTNAME: {peer['endpointHostname']}",
                "      TS_STATE_DIR: /var/lib/tailscale",
                '      TS_USERSPACE: "true"',
                f"      TS_SERVE_CONFIG: {serve_config_path(peer_id)}",
                "      TS_EXTRA_ARGS: --accept-dns=false",
                "    volumes:",
                f"      - {state_root}:/var/lib/tailscale",
                "      - ${BACKREST_DATA_ROOT}/generated:/generated:ro",
                "    networks:",
                f"      - {network_name}",
                "    restart: unless-stopped",
                "",
                f"  {backup_service}:",
                "    image: ${TAILSAFE_IMAGE_NAMESPACE}/tailsafe-rest-server:${TAILSAFE_VERSION}",
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
                "    networks:",
                f"      - {network_name}",
                "    restart: unless-stopped",
                "",
                f"  {maintenance_service}:",
                "    image: ${TAILSAFE_IMAGE_NAMESPACE}/tailsafe-rest-server:${TAILSAFE_VERSION}",
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
                "    networks:",
                f"      - {network_name}",
                "    restart: unless-stopped",
                "",
            ]
        )

    lines.extend(["networks:"])
    for peer in peers:
        network_name = endpoint_network_name(peer["id"])
        lines.extend(
            [
                f"  {network_name}:",
                "    driver: bridge",
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

    for peer in peers:
        serve_path = serve_config_output_path(compose_output_path, peer["id"])
        ensure_parent_dir(serve_path)
        with open(serve_path, "w", encoding="utf-8") as handle:
            json.dump(render_serve_config(peer["id"]), handle, indent=2)
            handle.write("\n")

    with open(manifest_output_path, "w", encoding="utf-8") as handle:
        json.dump(htpasswd_manifest(peers), handle, indent=2)
        handle.write("\n")


if __name__ == "__main__":
    if len(sys.argv) != 4:
        raise SystemExit(
            "usage: generate_runtime_assets.py <input.json> <compose-output.yaml> <manifest-output.json>"
        )
    main(sys.argv[1], sys.argv[2], sys.argv[3])
