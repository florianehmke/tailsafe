import json
import os
import subprocess
import sys
import tempfile
import unittest
import uuid


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
            },
            {
                "id": "friend-c",
                "endpointHostname": "friend-c-endpoint.ts.net",
                "backupUri": "rest:http://backup-c:${TAILSAFE_REMOTE_BACKUP_HTTP_PASSWORD_FRIEND_C}@friend-c-endpoint.ts.net:8000/friend-c",
                "maintenanceUri": "rest:http://maint-c:${TAILSAFE_REMOTE_MAINT_HTTP_PASSWORD_FRIEND_C}@friend-c-endpoint.ts.net:8001/friend-c",
                "repositoryPassword": "${RESTIC_REPOSITORY_PASSWORD}",
                "checkCron": "10 4 * * 1",
                "forgetCron": "20 4 * * 1",
                "pruneCron": "30 4 * * 1",
                "retention": {
                    "daily": 14,
                    "weekly": 4,
                    "monthly": 6,
                    "yearly": 1,
                },
                "healthchecks": {
                    "check": "https://hc-ping.com/friend-c-check-uuid",
                    "forget": "https://hc-ping.com/friend-c-forget-uuid",
                    "prune": "https://hc-ping.com/friend-c-prune-uuid",
                },
            },
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
                "destinationIds": ["friend-b", "friend-c"],
                "healthchecks": {
                    "backup": "https://hc-ping.com/photos-uuid",
                },
            },
            {
                "id": "volsync-prod",
                "paths": ["/userdata/volsync/prod"],
                "excludes": [],
                "destinationIds": ["friend-c"],
                "healthchecks": {
                    "backup": "https://hc-ping.com/volsync-prod-uuid",
                },
            },
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
                "excludes": ["**/.DS_Store"],
                "healthchecks": {
                    "backup": "https://hc-ping.com/photos-uuid",
                },
            }
        ],
    }


class GenerateBackrestConfigTest(unittest.TestCase):
    maxDiff = None

    def multisite_env(self) -> dict[str, str]:
        return {
            "TAILSAFE_REMOTE_BACKUP_HTTP_PASSWORD_FRIEND_B": "remote-backup-password-b",
            "TAILSAFE_REMOTE_MAINT_HTTP_PASSWORD_FRIEND_B": "remote-maint-password-b",
            "TAILSAFE_REMOTE_BACKUP_HTTP_PASSWORD_FRIEND_C": "remote-backup-password-c",
            "TAILSAFE_REMOTE_MAINT_HTTP_PASSWORD_FRIEND_C": "remote-maint-password-c",
            "TAILSAFE_INBOUND_BACKUP_HTTP_PASSWORD_FRIEND_B": "local-backup-password-b",
            "TAILSAFE_INBOUND_MAINT_HTTP_PASSWORD_FRIEND_B": "local-maint-password-b",
            "TAILSAFE_INBOUND_BACKUP_HTTP_PASSWORD_FRIEND_C": "local-backup-password-c",
            "TAILSAFE_INBOUND_MAINT_HTTP_PASSWORD_FRIEND_C": "local-maint-password-c",
            "RESTIC_REPOSITORY_PASSWORD": "repo-password",
        }

    def run_generator_to(
        self,
        output_path: str,
        site_config: dict | None = None,
        env: dict[str, str] | None = None,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "site.json")
            with open(input_path, "w", encoding="utf-8") as handle:
                json.dump(site_config or multisite_site_config(), handle)

            subprocess.run(
                [
                    sys.executable,
                    "scripts/generate_backrest_config.py",
                    input_path,
                    output_path,
                ],
                check=True,
                env=os.environ | (env or self.multisite_env()),
            )

    def load_repos(self, output_path: str) -> dict[str, dict]:
        with open(output_path, "r", encoding="utf-8") as handle:
            config = json.load(handle)
        return {repo["id"]: repo for repo in config["repos"]}

    def run_generator(self, site_config: dict, env: dict[str, str]) -> dict:
        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "site.json")
            output_path = os.path.join(tmpdir, "config.json")

            with open(input_path, "w", encoding="utf-8") as handle:
                json.dump(site_config, handle)

            subprocess.run(
                [
                    sys.executable,
                    "scripts/generate_backrest_config.py",
                    input_path,
                    output_path,
                ],
                check=True,
                env=os.environ | env,
            )

            with open(output_path, "r", encoding="utf-8") as handle:
                return json.load(handle)

    def test_generator_creates_multi_remote_repos_and_plans(self) -> None:
        config = self.run_generator(
            multisite_site_config(),
            {
                "TAILSAFE_REMOTE_BACKUP_HTTP_PASSWORD_FRIEND_B": "remote-backup-password-b",
                "TAILSAFE_REMOTE_MAINT_HTTP_PASSWORD_FRIEND_B": "remote-maint-password-b",
                "TAILSAFE_REMOTE_BACKUP_HTTP_PASSWORD_FRIEND_C": "remote-backup-password-c",
                "TAILSAFE_REMOTE_MAINT_HTTP_PASSWORD_FRIEND_C": "remote-maint-password-c",
                "TAILSAFE_INBOUND_BACKUP_HTTP_PASSWORD_FRIEND_B": "local-backup-password-b",
                "TAILSAFE_INBOUND_MAINT_HTTP_PASSWORD_FRIEND_B": "local-maint-password-b",
                "TAILSAFE_INBOUND_BACKUP_HTTP_PASSWORD_FRIEND_C": "local-backup-password-c",
                "TAILSAFE_INBOUND_MAINT_HTTP_PASSWORD_FRIEND_C": "local-maint-password-c",
                "RESTIC_REPOSITORY_PASSWORD": "repo-password",
                "TAILSAFE_BACKREST_GENERATED_DIR": "/custom-generated",
            },
        )

        repos_by_id = {repo["id"]: repo for repo in config["repos"]}
        plans_by_id = {plan["id"]: plan for plan in config["plans"]}

        self.assertEqual(
            set(repos_by_id),
            {
                "friend-b-backup",
                "friend-b-maintenance",
                "friend-c-backup",
                "friend-c-maintenance",
            },
        )
        self.assertEqual(
            set(plans_by_id),
            {"photos-to-friend-b", "photos-to-friend-c", "volsync-prod"},
        )

        self.assertEqual(plans_by_id["photos-to-friend-b"]["repo"], "friend-b-backup")
        self.assertEqual(plans_by_id["photos-to-friend-c"]["repo"], "friend-c-backup")
        self.assertEqual(plans_by_id["volsync-prod"]["repo"], "friend-c-backup")

        for plan in plans_by_id.values():
            self.assertEqual(plan["retention"], {"policyKeepAll": True})
            self.assertTrue(
                plan["hooks"][0]["actionCommand"]["command"].startswith(
                    "/custom-generated/bin/preflight.sh"
                )
            )

        friend_b_backup = repos_by_id["friend-b-backup"]
        friend_c_backup = repos_by_id["friend-c-backup"]
        friend_b_maintenance = repos_by_id["friend-b-maintenance"]
        friend_c_maintenance = repos_by_id["friend-c-maintenance"]

        self.assertIn("remote-backup-password-b", friend_b_backup["uri"])
        self.assertIn("remote-backup-password-c", friend_c_backup["uri"])
        self.assertEqual(friend_b_backup["password"], "repo-password")
        self.assertEqual(friend_c_backup["password"], "repo-password")

        for policy in ("checkPolicy", "prunePolicy", "forgetPolicy"):
            self.assertTrue(friend_b_backup[policy]["schedule"]["disabled"])
            self.assertTrue(friend_c_backup[policy]["schedule"]["disabled"])

        self.assertEqual(
            friend_b_maintenance["checkPolicy"]["schedule"],
            {"cron": "20 3 * * 0", "clock": "CLOCK_LOCAL"},
        )
        self.assertEqual(
            friend_c_maintenance["checkPolicy"]["schedule"],
            {"cron": "10 4 * * 1", "clock": "CLOCK_LOCAL"},
        )
        self.assertEqual(
            friend_c_maintenance["forgetPolicy"]["retention"],
            {
                "policyTimeBucketed": {
                    "daily": 14,
                    "weekly": 4,
                    "monthly": 6,
                    "yearly": 1,
                }
            },
        )

        self.assertEqual(
            {
                hook["actionHealthchecks"]["webhookUrl"]
                for hook in friend_b_maintenance["hooks"]
            },
            {
                "https://hc-ping.com/friend-b-check-uuid",
                "https://hc-ping.com/friend-b-forget-uuid",
                "https://hc-ping.com/friend-b-prune-uuid",
            },
        )
        self.assertEqual(
            {
                hook["actionHealthchecks"]["webhookUrl"]
                for hook in friend_c_maintenance["hooks"]
            },
            {
                "https://hc-ping.com/friend-c-check-uuid",
                "https://hc-ping.com/friend-c-forget-uuid",
                "https://hc-ping.com/friend-c-prune-uuid",
            },
        )

    def test_generator_accepts_legacy_remote_schema(self) -> None:
        config = self.run_generator(
            legacy_site_config(),
            {
                "TAILSAFE_BACKUP_HTTP_PASSWORD": "backup-password",
                "TAILSAFE_MAINT_HTTP_PASSWORD": "maint-password",
                "RESTIC_REPOSITORY_PASSWORD": "repo-password",
            },
        )

        repos_by_id = {repo["id"]: repo for repo in config["repos"]}

        self.assertEqual(set(repos_by_id), {"friend-b-backup", "friend-b-maintenance"})
        self.assertEqual([plan["id"] for plan in config["plans"]], ["photos"])
        self.assertEqual(config["plans"][0]["repo"], "friend-b-backup")
        self.assertEqual(repos_by_id["friend-b-backup"]["password"], "repo-password")
        self.assertEqual(repos_by_id["friend-b-maintenance"]["password"], "repo-password")

    def test_repository_uri_passwords_are_url_encoded(self) -> None:
        config = self.run_generator(
            multisite_site_config(),
            {
                "TAILSAFE_REMOTE_BACKUP_HTTP_PASSWORD_FRIEND_B": "p@ss:word/foo",
                "TAILSAFE_REMOTE_MAINT_HTTP_PASSWORD_FRIEND_B": "maint@pass",
                "TAILSAFE_REMOTE_BACKUP_HTTP_PASSWORD_FRIEND_C": "backup-password-c",
                "TAILSAFE_REMOTE_MAINT_HTTP_PASSWORD_FRIEND_C": "maint-password-c",
                "TAILSAFE_INBOUND_BACKUP_HTTP_PASSWORD_FRIEND_B": "local-backup-password-b",
                "TAILSAFE_INBOUND_MAINT_HTTP_PASSWORD_FRIEND_B": "local-maint-password-b",
                "TAILSAFE_INBOUND_BACKUP_HTTP_PASSWORD_FRIEND_C": "local-backup-password-c",
                "TAILSAFE_INBOUND_MAINT_HTTP_PASSWORD_FRIEND_C": "local-maint-password-c",
                "RESTIC_REPOSITORY_PASSWORD": "repo@pass:word",
            },
        )

        repos_by_id = {repo["id"]: repo for repo in config["repos"]}
        backup_repo = repos_by_id["friend-b-backup"]
        maint_repo = repos_by_id["friend-b-maintenance"]

        self.assertIn("p%40ss%3Aword%2Ffoo", backup_repo["uri"])
        self.assertNotIn("p@ss:word/foo", backup_repo["uri"])
        self.assertIn("maint%40pass", maint_repo["uri"])
        self.assertNotIn("maint@pass", maint_repo["uri"])
        self.assertEqual(backup_repo["password"], "repo@pass:word")
        self.assertEqual(maint_repo["password"], "repo@pass:word")

    def test_generator_rejects_mixed_legacy_and_multi_remote_schema(self) -> None:
        site_config = multisite_site_config()
        site_config["remote"] = legacy_site_config()["remote"]

        with tempfile.TemporaryDirectory() as tmpdir:
            input_path = os.path.join(tmpdir, "site.json")
            output_path = os.path.join(tmpdir, "config.json")

            with open(input_path, "w", encoding="utf-8") as handle:
                json.dump(site_config, handle)

            result = subprocess.run(
                [
                    sys.executable,
                    "scripts/generate_backrest_config.py",
                    input_path,
                    output_path,
                ],
                check=False,
                env=os.environ
                | {
                    "TAILSAFE_REMOTE_BACKUP_HTTP_PASSWORD_FRIEND_B": "remote-backup-password-b",
                    "TAILSAFE_REMOTE_MAINT_HTTP_PASSWORD_FRIEND_B": "remote-maint-password-b",
                    "TAILSAFE_REMOTE_BACKUP_HTTP_PASSWORD_FRIEND_C": "remote-backup-password-c",
                    "TAILSAFE_REMOTE_MAINT_HTTP_PASSWORD_FRIEND_C": "remote-maint-password-c",
                    "TAILSAFE_INBOUND_BACKUP_HTTP_PASSWORD_FRIEND_B": "local-backup-password-b",
                    "TAILSAFE_INBOUND_MAINT_HTTP_PASSWORD_FRIEND_B": "local-maint-password-b",
                    "TAILSAFE_INBOUND_BACKUP_HTTP_PASSWORD_FRIEND_C": "local-backup-password-c",
                    "TAILSAFE_INBOUND_MAINT_HTTP_PASSWORD_FRIEND_C": "local-maint-password-c",
                    "RESTIC_REPOSITORY_PASSWORD": "repo-password",
                },
                capture_output=True,
                text=True,
            )

        self.assertNotEqual(result.returncode, 0)
        self.assertIn("must not define both", result.stderr)

    def test_first_render_omits_guid_for_generated_repos(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "config.json")
            self.run_generator_to(output_path)
            repos_by_id = self.load_repos(output_path)

            for repo_id in (
                "friend-b-backup",
                "friend-b-maintenance",
                "friend-c-backup",
                "friend-c-maintenance",
            ):
                with self.subTest(repo_id=repo_id):
                    repo = repos_by_id[repo_id]
                    self.assertNotIn("guid", repo)
                    self.assertTrue(repo["autoInitialize"])

    def test_rerender_preserves_valid_existing_guid(self) -> None:
        valid_backup_guid = "a" * 64
        valid_maint_guid = "b" * 64

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "config.json")
            self.run_generator_to(output_path)

            with open(output_path, "r", encoding="utf-8") as handle:
                config = json.load(handle)

            for repo in config["repos"]:
                if repo["id"] == "friend-b-backup":
                    repo["guid"] = valid_backup_guid
                elif repo["id"] == "friend-b-maintenance":
                    repo["guid"] = valid_maint_guid

            with open(output_path, "w", encoding="utf-8") as handle:
                json.dump(config, handle, indent=2)
                handle.write("\n")

            self.run_generator_to(output_path)
            repos_by_id = self.load_repos(output_path)

            self.assertEqual(repos_by_id["friend-b-backup"]["guid"], valid_backup_guid)
            self.assertFalse(repos_by_id["friend-b-backup"]["autoInitialize"])
            self.assertEqual(repos_by_id["friend-b-maintenance"]["guid"], valid_maint_guid)
            self.assertFalse(repos_by_id["friend-b-maintenance"]["autoInitialize"])
            self.assertNotIn("guid", repos_by_id["friend-c-backup"])
            self.assertTrue(repos_by_id["friend-c-backup"]["autoInitialize"])

    def test_rerender_ignores_invalid_uuid_style_guid(self) -> None:
        invalid_guid = str(uuid.uuid5(uuid.NAMESPACE_DNS, "friend-b-backup"))

        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "config.json")
            self.run_generator_to(output_path)

            with open(output_path, "r", encoding="utf-8") as handle:
                config = json.load(handle)

            for repo in config["repos"]:
                if repo["id"] == "friend-b-backup":
                    repo["guid"] = invalid_guid
                elif repo["id"] == "friend-b-maintenance":
                    repo["guid"] = str(uuid.uuid5(uuid.NAMESPACE_DNS, "friend-b-maintenance"))

            with open(output_path, "w", encoding="utf-8") as handle:
                json.dump(config, handle, indent=2)
                handle.write("\n")

            self.run_generator_to(output_path)
            repos_by_id = self.load_repos(output_path)

            for repo_id in (
                "friend-b-backup",
                "friend-b-maintenance",
                "friend-c-backup",
                "friend-c-maintenance",
            ):
                with self.subTest(repo_id=repo_id):
                    repo = repos_by_id[repo_id]
                    self.assertNotIn("guid", repo)
                    self.assertTrue(repo["autoInitialize"])
