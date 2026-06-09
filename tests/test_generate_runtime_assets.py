import json
import os
import subprocess
import sys
import tempfile
import unittest


def multisite_site_config() -> dict:
    return {
        "instance": "tailsafe-site-a",
        "auth": {"disabled": True},
        "outboundRemotes": [
            {
                "id": "friend-b",
                "endpointHostname": "friend-b-endpoint.ts.net",
                "backupUri": "rest:http://backup-b:${TAILSAFE_REMOTE_BACKUP_HTTP_PASSWORD_FRIEND_B}@friend-b-endpoint.ts.net:8000/friend-b",
                "maintenanceUri": "rest:http://maint-b:${TAILSAFE_REMOTE_MAINT_HTTP_PASSWORD_FRIEND_B}@friend-b-endpoint.ts.net:8001/friend-b",
                "repositoryPassword": "${RESTIC_REPOSITORY_PASSWORD}",
                "healthchecks": {
                    "check": "https://hc-ping.com/friend-b-check-uuid",
                    "forget": "https://hc-ping.com/friend-b-forget-uuid",
                    "prune": "https://hc-ping.com/friend-b-prune-uuid",
                },
            }
        ],
        "inboundPeers": [
            {
                "id": "friend-b",
                "endpointAuthKey": "${TS_ENDPOINT_AUTHKEY_FRIEND_B}",
                "endpointHostname": "tailsafe-endpoint-friend-b",
                "repositorySubdir": "friend-b",
                "backup": {
                    "user": "backup-b",
                    "password": "${TAILSAFE_INBOUND_BACKUP_HTTP_PASSWORD_FRIEND_B}",
                },
                "maintenance": {
                    "user": "maint-b",
                    "password": "${TAILSAFE_INBOUND_MAINT_HTTP_PASSWORD_FRIEND_B}",
                },
            },
            {
                "id": "friend-c",
                "endpointAuthKey": "${TS_ENDPOINT_AUTHKEY_FRIEND_C}",
                "endpointHostname": "tailsafe-endpoint-friend-c",
                "repositorySubdir": "friend-c",
                "backup": {
                    "user": "backup-c",
                    "password": "${TAILSAFE_INBOUND_BACKUP_HTTP_PASSWORD_FRIEND_C}",
                },
                "maintenance": {
                    "user": "maint-c",
                    "password": "${TAILSAFE_INBOUND_MAINT_HTTP_PASSWORD_FRIEND_C}",
                },
            },
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
                "yearly": 2,
            },
        },
        "sources": [
            {
                "id": "photos",
                "paths": ["/userdata/photos"],
                "excludes": ["**/.DS_Store"],
                "destinationIds": ["friend-b"],
                "healthchecks": {
                    "backup": "https://hc-ping.com/photos-uuid",
                },
            }
        ],
    }


def legacy_site_config() -> dict:
    return {
        "instance": "tailsafe-site-a",
        "auth": {"disabled": True},
        "remote": {
            "id": "friend-b",
            "backupUri": "rest:http://backup:${TAILSAFE_BACKUP_HTTP_PASSWORD}@friend-b-endpoint.ts.net:8000/friend-b",
            "maintenanceUri": "rest:http://maint:${TAILSAFE_MAINT_HTTP_PASSWORD}@friend-b-endpoint.ts.net:8001/friend-b",
            "repositoryPassword": "${RESTIC_REPOSITORY_PASSWORD}",
        },
        "defaults": {
            "backupCron": "15 2 * * *",
            "checkCron": "20 3 * * 0",
            "forgetCron": "35 3 * * 0",
            "pruneCron": "50 3 * * 0",
            "retention": {
                "daily": 30,
                "weekly": 8,
                "monthly": 12,
                "yearly": 2,
            },
        },
        "healthchecks": {
            "check": "https://hc-ping.com/check-uuid",
            "forget": "https://hc-ping.com/forget-uuid",
            "prune": "https://hc-ping.com/prune-uuid",
        },
        "sources": [
            {
                "id": "photos",
                "paths": ["/userdata/photos"],
                "excludes": [],
                "healthchecks": {
                    "backup": "https://hc-ping.com/photos-uuid",
                },
            }
        ],
    }


class GenerateRuntimeAssetsTest(unittest.TestCase):
    maxDiff = None

    def run_generator(
        self, site_config: dict, env: dict[str, str]
    ) -> tuple[str, dict, dict[str, dict]]:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "site.json")
            compose_path = os.path.join(tmpdir, "compose.endpoints.yaml")
            manifest_path = os.path.join(tmpdir, "htpasswd-manifest.json")

            with open(input_path, "w", encoding="utf-8") as handle:
                json.dump(site_config, handle)

            subprocess.run(
                [
                    sys.executable,
                    "scripts/generate_runtime_assets.py",
                    input_path,
                    compose_path,
                    manifest_path,
                ],
                check=True,
                env=os.environ | env,
            )

            with open(compose_path, "r", encoding="utf-8") as handle:
                compose_text = handle.read()
            with open(manifest_path, "r", encoding="utf-8") as handle:
                manifest = json.load(handle)

            serve_configs: dict[str, dict] = {}
            for peer in manifest.get("peers", []):
                peer_id = peer["id"]
                serve_path = os.path.join(tmpdir, f"tailscale-serve-{peer_id}.json")
                with open(serve_path, "r", encoding="utf-8") as handle:
                    serve_configs[peer_id] = json.load(handle)

            return compose_text, manifest, serve_configs

    def test_generator_creates_endpoint_trios_for_each_inbound_peer(self) -> None:
        compose_text, manifest, serve_configs = self.run_generator(
            multisite_site_config(),
            {
                "TAILSAFE_REMOTE_BACKUP_HTTP_PASSWORD_FRIEND_B": "remote-backup-password-b",
                "TAILSAFE_REMOTE_MAINT_HTTP_PASSWORD_FRIEND_B": "remote-maint-password-b",
                "TAILSAFE_REMOTE_BACKUP_HTTP_PASSWORD_FRIEND_C": "remote-backup-password-c",
                "TAILSAFE_REMOTE_MAINT_HTTP_PASSWORD_FRIEND_C": "remote-maint-password-c",
                "TAILSAFE_INBOUND_BACKUP_HTTP_PASSWORD_FRIEND_B": "backup-password-b",
                "TAILSAFE_INBOUND_MAINT_HTTP_PASSWORD_FRIEND_B": "maint-password-b",
                "TAILSAFE_INBOUND_BACKUP_HTTP_PASSWORD_FRIEND_C": "backup-password-c",
                "TAILSAFE_INBOUND_MAINT_HTTP_PASSWORD_FRIEND_C": "maint-password-c",
                "RESTIC_REPOSITORY_PASSWORD": "repo-password",
            },
        )

        self.assertNotIn("network_mode: service:", compose_text)
        self.assertIn("tailscale-endpoint-friend-b:", compose_text)
        self.assertIn("tailscale-endpoint-friend-c:", compose_text)
        self.assertIn("rest-server-backup-friend-b:", compose_text)
        self.assertIn("rest-server-maintenance-friend-c:", compose_text)
        self.assertIn("image: tailscale/tailscale:${TAILSCALE_DOCKER_TAG}", compose_text)
        self.assertIn("TS_AUTHKEY: ${TS_ENDPOINT_AUTHKEY_FRIEND_B}", compose_text)
        self.assertIn("TS_AUTHKEY: ${TS_ENDPOINT_AUTHKEY_FRIEND_C}", compose_text)
        self.assertIn('TS_AUTH_ONCE: "true"', compose_text)
        self.assertIn('TS_USERSPACE: "true"', compose_text)
        self.assertIn("TS_EXTRA_ARGS: --accept-dns=false", compose_text)
        self.assertIn("TS_HOSTNAME: tailsafe-endpoint-friend-b", compose_text)
        self.assertIn("TS_HOSTNAME: tailsafe-endpoint-friend-c", compose_text)
        self.assertIn(
            "TS_SERVE_CONFIG: /generated/tailscale-serve-friend-b.json", compose_text
        )
        self.assertIn(
            "TS_SERVE_CONFIG: /generated/tailscale-serve-friend-c.json", compose_text
        )
        self.assertIn("${TAILSAFE_STATE_ROOT}/endpoint-friend-b:/var/lib/tailscale", compose_text)
        self.assertIn("${TAILSAFE_STATE_ROOT}/endpoint-friend-c:/var/lib/tailscale", compose_text)
        self.assertIn("${BACKREST_DATA_ROOT}/generated:/generated:ro", compose_text)
        self.assertIn("${REPO_DATA_ROOT}/friend-b:/data", compose_text)
        self.assertIn("${REPO_DATA_ROOT}/friend-c:/data", compose_text)
        self.assertIn("/generated/rest-server-backup-friend-b.htpasswd", compose_text)
        self.assertIn("/generated/rest-server-maint-friend-c.htpasswd", compose_text)
        self.assertIn("endpoint-net-friend-b:", compose_text)
        self.assertIn("endpoint-net-friend-c:", compose_text)
        for peer_id in ("friend-b", "friend-c"):
            with self.subTest(peer_id=peer_id):
                self.assertIn(
                    f"  tailscale-endpoint-{peer_id}:\n"
                    "    image: tailscale/tailscale:${TAILSCALE_DOCKER_TAG}\n"
                    "    depends_on:\n"
                    "      configurator:\n"
                    "        condition: service_completed_successfully",
                    compose_text,
                )

        self.assertEqual(
            serve_configs["friend-b"]["TCP"]["8000"]["TCPForward"],
            "rest-server-backup-friend-b:8000",
        )
        self.assertEqual(
            serve_configs["friend-b"]["TCP"]["8001"]["TCPForward"],
            "rest-server-maintenance-friend-b:8001",
        )
        self.assertEqual(
            serve_configs["friend-c"]["TCP"]["8000"]["TCPForward"],
            "rest-server-backup-friend-c:8000",
        )
        self.assertEqual(
            serve_configs["friend-c"]["TCP"]["8001"]["TCPForward"],
            "rest-server-maintenance-friend-c:8001",
        )

        self.assertEqual(
            manifest,
            {
                "peers": [
                    {
                        "id": "friend-b",
                        "backupHtpasswdPath": "/generated/rest-server-backup-friend-b.htpasswd",
                        "backupUser": "backup-b",
                        "backupPassword": "backup-password-b",
                        "maintenanceHtpasswdPath": "/generated/rest-server-maint-friend-b.htpasswd",
                        "maintenanceUser": "maint-b",
                        "maintenancePassword": "maint-password-b",
                    },
                    {
                        "id": "friend-c",
                        "backupHtpasswdPath": "/generated/rest-server-backup-friend-c.htpasswd",
                        "backupUser": "backup-c",
                        "backupPassword": "backup-password-c",
                        "maintenanceHtpasswdPath": "/generated/rest-server-maint-friend-c.htpasswd",
                        "maintenanceUser": "maint-c",
                        "maintenancePassword": "maint-password-c",
                    },
                ]
            },
        )

    def test_generator_supports_legacy_single_endpoint_defaults(self) -> None:
        compose_text, manifest, serve_configs = self.run_generator(
            legacy_site_config(),
            {
                "TAILSAFE_BACKUP_HTTP_USER": "backup",
                "TAILSAFE_BACKUP_HTTP_PASSWORD": "backup-password",
                "TAILSAFE_MAINT_HTTP_USER": "maint",
                "TAILSAFE_MAINT_HTTP_PASSWORD": "maint-password",
                "RESTIC_REPOSITORY_PASSWORD": "repo-password",
            },
        )

        self.assertIn("tailscale-endpoint-friend-b:", compose_text)
        self.assertIn("TS_AUTHKEY: ${TS_ENDPOINT_AUTHKEY}", compose_text)
        self.assertIn("TS_HOSTNAME: ${TS_ENDPOINT_HOSTNAME}", compose_text)
        self.assertIn("${REPO_DATA_ROOT}/friend-b:/data", compose_text)

        self.assertEqual(
            manifest,
            {
                "peers": [
                    {
                        "id": "friend-b",
                        "backupHtpasswdPath": "/generated/rest-server-backup-friend-b.htpasswd",
                        "backupUser": "backup",
                        "backupPassword": "backup-password",
                        "maintenanceHtpasswdPath": "/generated/rest-server-maint-friend-b.htpasswd",
                        "maintenanceUser": "maint",
                        "maintenancePassword": "maint-password",
                    }
                ]
            },
        )

    def test_generator_rejects_duplicate_repository_subdirs(self) -> None:
        site_config = multisite_site_config()
        site_config["inboundPeers"][1]["repositorySubdir"] = "friend-b"

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "site.json")
            compose_path = os.path.join(tmpdir, "compose.endpoints.yaml")
            manifest_path = os.path.join(tmpdir, "htpasswd-manifest.json")

            with open(input_path, "w", encoding="utf-8") as handle:
                json.dump(site_config, handle)

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/generate_runtime_assets.py",
                    input_path,
                    compose_path,
                    manifest_path,
                ],
                check=False,
                env=os.environ
                | {
                    "TAILSAFE_REMOTE_BACKUP_HTTP_PASSWORD_FRIEND_B": "remote-backup-password-b",
                    "TAILSAFE_REMOTE_MAINT_HTTP_PASSWORD_FRIEND_B": "remote-maint-password-b",
                    "TAILSAFE_REMOTE_BACKUP_HTTP_PASSWORD_FRIEND_C": "remote-backup-password-c",
                    "TAILSAFE_REMOTE_MAINT_HTTP_PASSWORD_FRIEND_C": "remote-maint-password-c",
                    "TAILSAFE_INBOUND_BACKUP_HTTP_PASSWORD_FRIEND_B": "backup-password-b",
                    "TAILSAFE_INBOUND_MAINT_HTTP_PASSWORD_FRIEND_B": "maint-password-b",
                    "TAILSAFE_INBOUND_BACKUP_HTTP_PASSWORD_FRIEND_C": "backup-password-c",
                    "TAILSAFE_INBOUND_MAINT_HTTP_PASSWORD_FRIEND_C": "maint-password-c",
                    "RESTIC_REPOSITORY_PASSWORD": "repo-password",
                },
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("duplicate inbound repositorySubdir", result.stderr)
