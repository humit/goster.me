#!/usr/bin/env python3

from __future__ import annotations

import sqlite3
import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

import sandbox_app

from adapters import ResolvedContent
from shortlinks import ShortLinkStore


class SandboxStoreTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "links.sqlite3"
        self.store = ShortLinkStore(
            self.path,
            ttl_seconds=60,
            code_length=6,
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def _save(self, *, render_mode: str) -> str:
        item = ResolvedContent(
            kind="activity",
            provider="example",
            source_url="https://example.com/source",
            title="Example",
            content_url="https://example.com/activity",
            adapter="example",
            render_mode=render_mode,
            selector="#game",
        )
        return self.store.save(item, now=100)

    def test_loads_only_live_isolate_items(self):
        code = self._save(render_mode="isolate")

        with patch.object(sandbox_app, "DATABASE_PATH", self.path):
            item = sandbox_app.load_item_readonly(code, now=120)

        self.assertIsNotNone(item)
        self.assertEqual(item.render_mode, "isolate")

    def test_rejects_non_isolate_items(self):
        code = self._save(render_mode="embed")

        with patch.object(sandbox_app, "DATABASE_PATH", self.path):
            item = sandbox_app.load_item_readonly(code, now=120)

        self.assertIsNone(item)

    def test_rejects_expired_items_without_mutating_store(self):
        code = self._save(render_mode="isolate")

        with patch.object(sandbox_app, "DATABASE_PATH", self.path):
            item = sandbox_app.load_item_readonly(code, now=160)

        self.assertIsNone(item)
        self.assertIsNotNone(self.store.expires_at(code))

    def test_read_does_not_increment_access_count(self):
        code = self._save(render_mode="isolate")

        with patch.object(sandbox_app, "DATABASE_PATH", self.path):
            item = sandbox_app.load_item_readonly(code, now=120)

        self.assertIsNotNone(item)

        with sqlite3.connect(self.path) as db:
            access_count = db.execute(
                "SELECT access_count FROM short_links WHERE code = ?",
                (code,),
            ).fetchone()[0]

        self.assertEqual(access_count, 0)

    def test_rejects_invalid_code(self):
        with patch.object(sandbox_app, "DATABASE_PATH", self.path):
            self.assertIsNone(
                sandbox_app.load_item_readonly("../../etc/passwd", now=120)
            )

    def test_strips_known_external_tracking_scripts(self):
        html = '''
        <script src="https://www.googletagmanager.com/gtag/js?id=G-TEST"></script>
        <script src="https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js"></script>
        <script src="https://example.com/game.js"></script>
        '''

        cleaned = sandbox_app.strip_known_tracking_html(html)

        self.assertNotIn("googletagmanager.com", cleaned)
        self.assertNotIn("googlesyndication.com", cleaned)
        self.assertIn("https://example.com/game.js", cleaned)

    def test_strips_inline_gtag_bootstrap(self):
        html = '''
        <script>
        window.dataLayer = window.dataLayer || [];
        function gtag(){dataLayer.push(arguments);}
        gtag('config', 'G-TEST');
        </script>
        <script>window.gameStarted = true;</script>
        '''

        cleaned = sandbox_app.strip_known_tracking_html(html)

        self.assertNotIn("dataLayer", cleaned)
        self.assertNotIn("gtag(", cleaned)
        self.assertIn("window.gameStarted = true", cleaned)


if __name__ == "__main__":
    unittest.main()
