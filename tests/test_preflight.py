import os
import subprocess
import tempfile
import unittest


class PreflightTest(unittest.TestCase):
    def test_preflight_succeeds_when_paths_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            env = os.environ | {"RESTIC_REPOSITORY_PASSWORD": "repo-password"}
            subprocess.run(
                ["sh", "scripts/preflight.sh", "photos", tmpdir],
                check=True,
                env=env,
            )

    def test_preflight_fails_when_path_is_missing(self) -> None:
        env = os.environ | {"RESTIC_REPOSITORY_PASSWORD": "repo-password"}
        result = subprocess.run(
            ["sh", "scripts/preflight.sh", "photos", "/definitely-missing-path"],
            env=env,
            check=False,
            capture_output=True,
            text=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("missing backup path", result.stderr)
