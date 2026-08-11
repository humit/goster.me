#!/usr/bin/env python3

from __future__ import annotations

import unittest
from unittest.mock import patch

import platform_app

from adapters import ResolvedContent


class PlatformSandboxTests(unittest.TestCase):
    def test_resolver_allows_isolate_result_after_p0_hardening(self):
        sentinel = object()

        with patch.object(platform_app.app, "_ORIGINAL_RESOLVE_URL", return_value=sentinel):
            self.assertIs(platform_app.resolve_with_sandbox("https://example.com"), sentinel)

    def test_shell_uses_dedicated_sandbox_origin(self):
        item = ResolvedContent(
            kind="activity",
            provider="example",
            source_url="https://example.com/source",
            title="Example",
            content_url="https://example.com/activity",
            adapter="example",
            render_mode="isolate",
            selector="#game",
        )

        page = platform_app.render_sandbox_shell("abc346", item)

        self.assertIn("https://sandbox.goster.me/v/abc346", page)
        self.assertIn("sandbox=\"allow-scripts allow-modals allow-pointer-lock allow-presentation\"", page)
        self.assertNotIn("allow-same-origin", page)


if __name__ == "__main__":
    unittest.main()
