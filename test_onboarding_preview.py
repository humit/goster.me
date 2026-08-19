import unittest

from onboarding_demo import DEMO_ROUTE
from onboarding_preview import DEFAULT_HOST, DEFAULT_PORT, parse_args


class OnboardingPreviewTests(unittest.TestCase):
    def test_preview_binds_to_loopback_by_default(self):
        self.assertEqual(DEFAULT_HOST, "127.0.0.1")
        self.assertEqual(DEFAULT_PORT, 8093)

    def test_preview_uses_explicit_demo_route(self):
        self.assertEqual(DEMO_ROUTE, "/demo/activity")

    def test_preview_cli_can_override_port(self):
        args = parse_args(["--port", "9000"])
        self.assertEqual(args.host, "127.0.0.1")
        self.assertEqual(args.port, 9000)


if __name__ == "__main__":
    unittest.main()
