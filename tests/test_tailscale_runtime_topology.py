import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
COMPOSE = REPO_ROOT / "deploy/compose.example.yaml"
ENV_EXAMPLE = REPO_ROOT / "env.example"
ENV_ONE_FRIEND = REPO_ROOT / "env.one-friend.example"
WORKFLOW_CI = REPO_ROOT / ".github/workflows/ci.yml"
WORKFLOW_RELEASE = REPO_ROOT / ".github/workflows/release.yml"
LINT_SHELL = REPO_ROOT / ".cicd/scripts/lint-shell.sh"


def _service_block(text: str, service: str) -> str:
    pattern = rf"^  {re.escape(service)}:\n"
    match = re.search(pattern, text, re.MULTILINE)
    if match is None:
        return ""
    start = match.end()
    next_service = re.search(r"^  \w", text[start:], re.MULTILINE)
    end = start + next_service.start() if next_service else len(text)
    return text[start:end]


class TailscaleRuntimeTopologyTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.compose_text = COMPOSE.read_text(encoding="utf-8")
        cls.outbound_block = _service_block(cls.compose_text, "tailscale-outbound")
        cls.backrest_block = _service_block(cls.compose_text, "backrest")

    def test_tailscale_outbound_uses_official_tailscale_image(self) -> None:
        self.assertIn(
            "image: tailscale/tailscale:${TAILSCALE_DOCKER_TAG}",
            self.outbound_block,
        )

    def test_tailscale_outbound_env_and_network(self) -> None:
        for needle in (
            'TS_AUTH_ONCE: "true"',
            'TS_USERSPACE: "true"',
            "TS_OUTBOUND_HTTP_PROXY_LISTEN: :1055",
            "TS_EXTRA_ARGS: --accept-dns=false",
        ):
            with self.subTest(needle=needle):
                self.assertIn(needle, self.outbound_block)
        self.assertIn("networks:", self.outbound_block)
        self.assertNotIn("ports:", self.outbound_block)

    def test_backrest_uses_bridge_network_not_shared_namespace(self) -> None:
        self.assertNotIn("network_mode:", self.backrest_block)
        self.assertIn("networks:", self.backrest_block)
        self.assertIn("- tailsafe-outbound", self.backrest_block)
        for key in ("HTTP_PROXY:", "HTTPS_PROXY:", "http_proxy:", "https_proxy:"):
            with self.subTest(key=key):
                self.assertIn("http://tailscale-outbound:1055", self.backrest_block)
        self.assertIn(
            "127.0.0.1:${BACKREST_BIND_PORT}:9898",
            self.backrest_block,
        )

    def test_env_examples_define_tailscale_docker_tag(self) -> None:
        for path in (ENV_EXAMPLE, ENV_ONE_FRIEND):
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertIn("TAILSCALE_DOCKER_TAG=stable", text)
                after_version = text.split("TAILSAFE_VERSION=0.2.3\n", 1)[1]
                self.assertTrue(
                    after_version.startswith("TAILSCALE_DOCKER_TAG=stable\n"),
                    msg=f"{path.name}: TAILSCALE_DOCKER_TAG must follow TAILSAFE_VERSION",
                )

    def test_compose_defines_tailsafe_outbound_network(self) -> None:
        self.assertIn("networks:", self.compose_text)
        self.assertIn("tailsafe-outbound:", self.compose_text)
        self.assertIn("driver: bridge", self.compose_text)

    def test_workflows_do_not_build_custom_tailscale_image(self) -> None:
        for path in (WORKFLOW_CI, WORKFLOW_RELEASE):
            with self.subTest(path=path.name):
                text = path.read_text(encoding="utf-8")
                self.assertNotIn("tailsafe-tailscale", text)

    def test_lint_shell_does_not_reference_tailscale_entrypoint(self) -> None:
        text = LINT_SHELL.read_text(encoding="utf-8")
        self.assertNotIn("containers/tailscale/entrypoint.sh", text)


if __name__ == "__main__":
    unittest.main()
