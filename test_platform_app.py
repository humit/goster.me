#!/usr/bin/env python3

from __future__ import annotations

import unittest
from unittest.mock import patch

import platform_app

from adapters import ResolvedContent


TEST_KEY = "k" * 32


class PlatformSandboxTests(unittest.TestCase):
    def test_resolver_allows_isolate_result_after_p0_hardening(self):
        sentinel = object()

        with patch.object(platform_app.app, "_ORIGINAL_RESOLVE_URL", return_value=sentinel):
            self.assertIs(platform_app.resolve_with_sandbox("https://example.com"), sentinel)

    def test_shell_uses_signed_dedicated_sandbox_origin_with_storage_compat(self):
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

        with patch.dict(
            "os.environ",
            {"GOSTER_SANDBOX_SIGNING_KEY": TEST_KEY},
            clear=False,
        ):
            page = platform_app.render_sandbox_shell("abc346", item)

        self.assertIn("https://s.goster.me/v/abc346?exp=", page)
        self.assertIn("&amp;sig=", page)
        self.assertIn(
            "sandbox=\"allow-scripts allow-same-origin allow-modals "
            "allow-pointer-lock allow-presentation\"",
            page,
        )

    def test_shell_fails_closed_without_signing_key(self):
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

        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                platform_app.render_sandbox_shell("abc346", item)

    def test_server_header_does_not_expose_python_version(self):
        self.assertEqual(platform_app.Handler.server_version, "goster.me")
        self.assertEqual(platform_app.Handler.sys_version, "")


if __name__ == "__main__":
    unittest.main()
