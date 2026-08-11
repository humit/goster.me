#!/usr/bin/env python3

from __future__ import annotations

import sqlite3
import tempfile
import unittest

from pathlib import Path

from adapters import ResolvedContent
from shortlinks import ShortLinkStore
from storage_maintenance import maintain_database


class StorageMaintenanceTests(unittest.TestCase):
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
            source_url="https://example.com/source",
            title="Example",
            content_url="https://example.com/embed",
            adapter="example",
            render_mode="embed",
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_purges_expired_rows(self):
        self.store.save(self.item, now=100)
        self.store.save(self.item, now=200)

        stats = maintain_database(
            self.path,
            now=170,
            max_rows=10,
            target_rows=8,
            max_bytes=8 * 1024 * 1024,
        )

        self.assertEqual(stats["expired"], 1)
        self.assertEqual(stats["remaining"], 1)

    def test_trims_oldest_rows_to_target(self):
        for timestamp in range(100, 106):
            self.store.save(self.item, now=timestamp)

        stats = maintain_database(
            self.path,
            now=120,
            max_rows=5,
            target_rows=3,
            max_bytes=8 * 1024 * 1024,
        )

        self.assertEqual(stats["trimmed"], 3)
        self.assertEqual(stats["remaining"], 3)

    def test_persists_page_cap(self):
        maintain_database(
            self.path,
            now=120,
            max_rows=10,
            target_rows=8,
            max_bytes=4 * 1024 * 1024,
        )

        with sqlite3.connect(self.path) as db:
            page_size = int(db.execute("PRAGMA page_size").fetchone()[0])
            max_pages = int(db.execute("PRAGMA max_page_count").fetchone()[0])

        self.assertLessEqual(max_pages * page_size, 4 * 1024 * 1024)
        self.assertGreater(max_pages, 0)


if __name__ == "__main__":
    unittest.main()
