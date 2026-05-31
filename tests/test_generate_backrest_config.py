import json
import os
import subprocess
import sys
import tempfile
import unittest


class GenerateBackrestConfigTest(unittest.TestCase):
    def test_generator_creates_backup_and_maintenance_repos(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "config.json")
            env = os.environ | {
                "TAILSAFE_BACKUP_HTTP_PASSWORD": "backup-password",
                "TAILSAFE_MAINT_HTTP_PASSWORD": "maint-password",
                "RESTIC_REPOSITORY_PASSWORD": "repo-password",
            }
            subprocess.run(
                [
                    sys.executable,
                    "scripts/generate_backrest_config.py",
                    "tests/fixtures/site.example.json",
                    output_path,
                ],
                check=True,
                env=env,
            )

            with open(output_path, "r", encoding="utf-8") as handle:
                config = json.load(handle)

            repos_by_id = {repo["id"]: repo for repo in config["repos"]}
            backup_repo = repos_by_id["friend-b-backup"]
            maint_repo = repos_by_id["friend-b-maintenance"]
            plan = config["plans"][0]

            self.assertEqual(set(repos_by_id), {"friend-b-backup", "friend-b-maintenance"})
            self.assertEqual(plan["repo"], "friend-b-backup")
            self.assertIn("backup-password", backup_repo["uri"])
            self.assertIn("maint-password", maint_repo["uri"])
            self.assertTrue(
                backup_repo["uri"].startswith("rest:http://"),
                backup_repo["uri"],
            )
            self.assertTrue(
                maint_repo["uri"].startswith("rest:http://"),
                maint_repo["uri"],
            )
            self.assertEqual(backup_repo["password"], "repo-password")
            self.assertEqual(maint_repo["password"], "repo-password")

            for policy in ("checkPolicy", "prunePolicy", "forgetPolicy"):
                self.assertTrue(backup_repo[policy]["schedule"]["disabled"])

            self.assertEqual(plan["retention"], {"policyKeepAll": True})

            self.assertEqual(
                maint_repo["checkPolicy"]["schedule"],
                {"cron": "20 3 * * 0", "clock": "CLOCK_LOCAL"},
            )
            self.assertEqual(
                maint_repo["forgetPolicy"]["schedule"],
                {"cron": "35 3 * * 0", "clock": "CLOCK_LOCAL"},
            )
            self.assertEqual(
                maint_repo["prunePolicy"]["schedule"],
                {"cron": "50 3 * * 0", "clock": "CLOCK_LOCAL"},
            )
            self.assertEqual(
                maint_repo["forgetPolicy"]["retention"],
                {
                    "policyTimeBucketed": {
                        "daily": 30,
                        "weekly": 8,
                        "monthly": 12,
                        "yearly": 2,
                    }
                },
            )

            hook_urls = {
                hook["actionHealthchecks"]["webhookUrl"]
                for hook in maint_repo["hooks"]
            }
            self.assertEqual(
                hook_urls,
                {
                    "https://hc-ping.com/check-uuid",
                    "https://hc-ping.com/forget-uuid",
                    "https://hc-ping.com/prune-uuid",
                },
            )

    def test_repository_uri_passwords_are_url_encoded(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = os.path.join(tmpdir, "config.json")
            env = os.environ | {
                "TAILSAFE_BACKUP_HTTP_PASSWORD": "p@ss:word/foo",
                "TAILSAFE_MAINT_HTTP_PASSWORD": "maint@pass",
                "RESTIC_REPOSITORY_PASSWORD": "repo@pass:word",
            }
            subprocess.run(
                [
                    sys.executable,
                    "scripts/generate_backrest_config.py",
                    "tests/fixtures/site.example.json",
                    output_path,
                ],
                check=True,
                env=env,
            )

            with open(output_path, "r", encoding="utf-8") as handle:
                config = json.load(handle)

            repos_by_id = {repo["id"]: repo for repo in config["repos"]}
            backup_repo = repos_by_id["friend-b-backup"]
            maint_repo = repos_by_id["friend-b-maintenance"]

            self.assertIn("p%40ss%3Aword%2Ffoo", backup_repo["uri"])
            self.assertNotIn("p@ss:word/foo", backup_repo["uri"])
            self.assertIn("maint%40pass", maint_repo["uri"])
            self.assertNotIn("maint@pass", maint_repo["uri"])
            self.assertEqual(backup_repo["password"], "repo@pass:word")
            self.assertEqual(maint_repo["password"], "repo@pass:word")
