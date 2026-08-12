#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest

from pathlib import Path

from adapters import ResolvedContent
from shortlinks import ShortLinkStore
from feedback import FeedbackStore
from storage_maintenance import maintain_database
from unsupported import UnsupportedTargetStore


class StorageMaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "links.sqlite3"
        self.store = ShortLinkStore(
            self.path,
            ttl_seconds=60,
            code_length=6,
            database_max_bytes=8 * 1024 * 1024,
            max_rows=100,
            target_rows=80,
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

    def test_purges_expired_feedback(self):
        feedback = FeedbackStore(
            self.path,
            database_max_bytes=8 * 1024 * 1024,
            max_rows=100,
            target_rows=80,
        )
        feedback.submit("problem", "Eski geri bildirim", now=100)

        stats = maintain_database(
            self.path,
            now=100 + 91 * 24 * 60 * 60,
            max_rows=10,
            target_rows=8,
            max_bytes=8 * 1024 * 1024,
        )

        self.assertEqual(stats["feedback_purged"], 1)

    def test_purges_stale_unsupported_targets(self):
        unsupported = UnsupportedTargetStore(self.path)
        unsupported.record("https://example.com/old", now=100)
        stats = maintain_database(
            self.path,
            now=100 + 31 * 24 * 60 * 60,
            max_rows=10,
            target_rows=8,
            max_bytes=8 * 1024 * 1024,
        )
        self.assertEqual(stats["unsupported_purged"], 1)

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

    def test_applies_page_cap_to_maintenance_connection(self):
        stats = maintain_database(
            self.path,
            now=120,
            max_rows=10,
            target_rows=8,
            max_bytes=4 * 1024 * 1024,
        )

        self.assertLessEqual(
            stats["max_pages_this_connection"] * stats["page_size"],
            4 * 1024 * 1024,
        )
        self.assertGreater(stats["max_pages_this_connection"], 0)

    def test_store_applies_page_cap_on_each_connection(self):
        capped = ShortLinkStore(
            self.path,
            ttl_seconds=60,
            code_length=6,
            database_max_bytes=4 * 1024 * 1024,
            max_rows=100,
            target_rows=80,
        )

        with capped._connect() as db:
            page_size = int(db.execute("PRAGMA page_size").fetchone()[0])
            max_pages = int(db.execute("PRAGMA max_page_count").fetchone()[0])

        self.assertLessEqual(max_pages * page_size, 4 * 1024 * 1024)

    def test_store_trims_before_write_at_row_ceiling(self):
        capped = ShortLinkStore(
            self.path,
            ttl_seconds=1000,
            code_length=6,
            database_max_bytes=8 * 1024 * 1024,
            max_rows=5,
            target_rows=3,
        )

        for timestamp in range(100, 106):
            capped.save(self.item, now=timestamp)

        with capped._connect() as db:
            rows = int(db.execute("SELECT COUNT(*) FROM short_links").fetchone()[0])

        self.assertLessEqual(rows, 5)

    def test_rejects_oversized_payload(self):
        capped = ShortLinkStore(
            self.path,
            ttl_seconds=60,
            code_length=6,
            database_max_bytes=8 * 1024 * 1024,
            max_rows=100,
            target_rows=80,
            max_payload_bytes=128,
        )

        with self.assertRaises(ValueError):
            capped.save(self.item, now=100)


if __name__ == "__main__":
    unittest.main()
