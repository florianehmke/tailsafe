import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
ENTRYPOINT = REPO_ROOT / "containers/tailscale/entrypoint.sh"
COMPOSE = REPO_ROOT / "deploy/compose.example.yaml"


class TailscaleOutboundProxyTest(unittest.TestCase):
    def test_entrypoint_starts_tailscaled_with_userspace_and_local_proxy_flags(
        self,
    ) -> None:
        text = ENTRYPOINT.read_text(encoding="utf-8")
        self.assertIn("--tun=userspace-networking", text)
        self.assertIn(
            'proxy_listen="${TS_OUTBOUND_PROXY_LISTEN:-localhost:1055}"',
            text,
        )
        self.assertIn('--socks5-server="${proxy_listen}"', text)
        self.assertIn('--outbound-http-proxy-listen="${proxy_listen}"', text)

    def test_compose_tailscale_outbound_sets_proxy_listen_env(self) -> None:
        text = COMPOSE.read_text(encoding="utf-8")
        outbound_block = text.split("tailscale-outbound:", 1)[1].split("\n\n", 1)[0]
        self.assertIn("TS_OUTBOUND_PROXY_LISTEN:", outbound_block)
        self.assertIn("localhost:1055", outbound_block)

    def test_compose_backrest_has_outbound_proxy_env(self) -> None:
        text = COMPOSE.read_text(encoding="utf-8")
        backrest_block = text.split("  backrest:", 1)[1].split("\n\n", 1)[0]
        for key in (
            "HTTP_PROXY:",
            "HTTPS_PROXY:",
            "NO_PROXY:",
            "http_proxy:",
            "https_proxy:",
            "no_proxy:",
        ):
            with self.subTest(key=key):
                self.assertIn(key, backrest_block)
        self.assertIn("http://127.0.0.1:1055", backrest_block)
        self.assertIn("hc-ping.com", backrest_block)
        self.assertRegex(backrest_block, r"NO_PROXY:.*127\.0\.0\.1")
        self.assertRegex(backrest_block, r"NO_PROXY:.*localhost")


if __name__ == "__main__":
    unittest.main()
