#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest

from pathlib import Path

from adapters import ResolvedContent
from shortlinks import (
    SHORT_CODE_ALPHABET,
    ShortLinkStore,
)


class ShortLinkStoreTest(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "links.sqlite3"
        self.store = ShortLinkStore(
            self.path,
            ttl_seconds=60,
            code_length=6,
        )
        self.item = ResolvedContent(
            kind="embed",
            provider="example",
            source_url="https://example.com/very/long/source/url",
            title="Example",
            content_url="https://example.com/embed/1",
            content_urls=(
                "https://example.com/embed/1",
                "https://example.com/embed/2",
            ),
            adapter="example-adapter",
            render_mode="embed-collection",
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_code_is_human_friendly(self):
        code = self.store.save(
            self.item,
            now=100,
        )

        self.assertEqual(len(code), 6)
        self.assertTrue(
            all(ch in SHORT_CODE_ALPHABET for ch in code)
        )
        self.assertNotRegex(code, r"[0125oilz]")

    def test_item_survives_store_recreation(self):
        code = self.store.save(
            self.item,
            now=100,
        )

        reopened = ShortLinkStore(
            self.path,
            ttl_seconds=60,
            code_length=6,
        )

        loaded = reopened.get(
            code,
            now=120,
            touch=False,
        )

        self.assertEqual(loaded, self.item)
        self.assertIsInstance(
            loaded.content_urls,
            tuple,
        )

    def test_expired_item_is_removed(self):
        code = self.store.save(
            self.item,
            now=100,
        )

        self.assertIsNone(
            self.store.get(
                code,
                now=160,
            )
        )
        self.assertIsNone(
            self.store.expires_at(code)
        )

    def test_purge_expired_keeps_live_rows(self):
        old_code = self.store.save(
            self.item,
            now=100,
        )
        live_code = self.store.save(
            self.item,
            now=200,
        )

        self.assertEqual(
            self.store.purge_expired(now=170),
            1,
        )
        self.assertIsNone(
            self.store.get(old_code, now=170)
        )
        self.assertIsNotNone(
            self.store.get(
                live_code,
                now=220,
                touch=False,
            )
        )


if __name__ == "__main__":
    unittest.main()
