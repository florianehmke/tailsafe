import json
import os
import re
from urllib.parse import quote

ENV_PATTERN = re.compile(r"\$\{([A-Z0-9_]+)\}")
ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]*$")


def load_site(path: str) -> dict:
    with open(path, "r", encoding="utf-8") as handle:
        return json.load(handle)


def expand_env(value: str, *, url_encode: bool = False) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in os.environ:
            raise KeyError(f"missing environment variable: {key}")
        env_value = os.environ[key]
        if url_encode:
            return quote(env_value, safe="")
        return env_value

    return ENV_PATTERN.sub(replace, value)


def require_keys(context: str, item: dict, keys: list[str]) -> None:
    for key in keys:
        if key not in item:
            raise KeyError(f"{context} is missing required field: {key}")


def validate_identifier(value: str, context: str) -> str:
    if not ID_PATTERN.match(value):
        raise ValueError(
            f"{context} must match {ID_PATTERN.pattern!r}, got {value!r}"
        )
    return value


def validate_relative_subdir(value: str) -> str:
    if not value:
        raise ValueError("repositorySubdir must not be empty")
    if os.path.isabs(value):
        raise ValueError("repositorySubdir must be relative")

    normalized = os.path.normpath(value)
    if normalized in (".", "") or normalized == ".." or normalized.startswith("../"):
        raise ValueError("repositorySubdir must stay within REPO_DATA_ROOT")
    return normalized


def outbound_remotes(site: dict) -> list[dict]:
    if "outboundRemotes" in site and "remote" in site:
        raise ValueError(
            "site.json must not define both outboundRemotes and the legacy remote object"
        )

    if "outboundRemotes" in site:
        remotes = site["outboundRemotes"]
    elif "remote" in site:
        remote = site["remote"]
        remotes = [
            {
                "id": remote["id"],
                "endpointHostname": remote.get("endpointHostname"),
                "backupUri": remote["backupUri"],
                "maintenanceUri": remote["maintenanceUri"],
                "repositoryPassword": remote["repositoryPassword"],
                "healthchecks": site["healthchecks"],
            }
        ]
    else:
        remotes = []

    seen_ids: set[str] = set()
    seen_subdirs: set[str] = set()
    normalized: list[dict] = []

    for remote in remotes:
        require_keys(
            "outbound remote",
            remote,
            ["id", "backupUri", "maintenanceUri", "repositoryPassword", "healthchecks"],
        )
        remote_id = validate_identifier(remote["id"], "outbound remote id")
        if remote_id in seen_ids:
            raise ValueError(f"duplicate outbound remote id: {remote_id}")
        seen_ids.add(remote_id)
        require_keys(
            f"outbound remote {remote_id} healthchecks",
            remote["healthchecks"],
            ["check", "forget", "prune"],
        )
        normalized.append(remote)

    return normalized


def inbound_peers(site: dict) -> list[dict]:
    if "outboundRemotes" in site and "remote" in site:
        raise ValueError(
            "site.json must not define both outboundRemotes and the legacy remote object"
        )

    if "inboundPeers" in site:
        peers = site["inboundPeers"]
    elif "remote" in site:
        remote_id = validate_identifier(site["remote"]["id"], "legacy remote id")
        peers = [
            {
                "id": remote_id,
                "endpointAuthKey": "${TS_ENDPOINT_AUTHKEY}",
                "endpointHostname": "${TS_ENDPOINT_HOSTNAME}",
                "repositorySubdir": remote_id,
                "backup": {
                    "user": "${TAILSAFE_BACKUP_HTTP_USER}",
                    "password": "${TAILSAFE_BACKUP_HTTP_PASSWORD}",
                },
                "maintenance": {
                    "user": "${TAILSAFE_MAINT_HTTP_USER}",
                    "password": "${TAILSAFE_MAINT_HTTP_PASSWORD}",
                },
            }
        ]
    else:
        peers = []

    seen_ids: set[str] = set()
    seen_subdirs: set[str] = set()
    normalized: list[dict] = []

    for peer in peers:
        require_keys(
            "inbound peer",
            peer,
            [
                "id",
                "endpointAuthKey",
                "endpointHostname",
                "repositorySubdir",
                "backup",
                "maintenance",
            ],
        )
        peer_id = validate_identifier(peer["id"], "inbound peer id")
        if peer_id in seen_ids:
            raise ValueError(f"duplicate inbound peer id: {peer_id}")
        seen_ids.add(peer_id)
        require_keys(
            f"inbound peer {peer_id} backup auth",
            peer["backup"],
            ["user", "password"],
        )
        require_keys(
            f"inbound peer {peer_id} maintenance auth",
            peer["maintenance"],
            ["user", "password"],
        )
        repository_subdir = validate_relative_subdir(peer["repositorySubdir"])
        if repository_subdir in seen_subdirs:
            raise ValueError(
                f"duplicate inbound repositorySubdir: {repository_subdir}"
            )
        seen_subdirs.add(repository_subdir)

        normalized.append(
            {
                **peer,
                "id": peer_id,
                "repositorySubdir": repository_subdir,
            }
        )

    return normalized


def source_destination_ids(source: dict, outbound_remote_ids: list[str]) -> list[str]:
    destination_ids = source.get("destinationIds")
    if destination_ids is None:
        if len(outbound_remote_ids) == 1:
            destination_ids = [outbound_remote_ids[0]]
        else:
            raise KeyError(
                f"source {source['id']!r} must define destinationIds when multiple outbound remotes exist"
            )

    if not destination_ids:
        raise ValueError(f"source {source['id']!r} must target at least one destination")

    seen_ids: set[str] = set()
    normalized: list[str] = []
    for destination_id in destination_ids:
        validate_identifier(destination_id, "destination id")
        if destination_id not in outbound_remote_ids:
            raise ValueError(
                f"source {source['id']!r} references unknown destination {destination_id!r}"
            )
        if destination_id not in seen_ids:
            normalized.append(destination_id)
            seen_ids.add(destination_id)
    return normalized


def plan_id(source_id: str, destination_ids: list[str], destination_id: str) -> str:
    validate_identifier(source_id, "source id")
    if len(destination_ids) == 1:
        return source_id
    return f"{source_id}-to-{destination_id}"


def backup_htpasswd_path(peer_id: str) -> str:
    validate_identifier(peer_id, "inbound peer id")
    return f"/generated/rest-server-backup-{peer_id}.htpasswd"


def maintenance_htpasswd_path(peer_id: str) -> str:
    validate_identifier(peer_id, "inbound peer id")
    return f"/generated/rest-server-maint-{peer_id}.htpasswd"


def endpoint_network_name(peer_id: str) -> str:
    validate_identifier(peer_id, "inbound peer id")
    return f"endpoint-net-{peer_id}"


def serve_config_path(peer_id: str) -> str:
    validate_identifier(peer_id, "inbound peer id")
    return f"/generated/tailscale-serve-{peer_id}.json"
