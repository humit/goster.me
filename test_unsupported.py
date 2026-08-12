#!/usr/bin/env python3

from __future__ import annotations

import sqlite3
import tempfile
import unittest

from pathlib import Path

from unsupported import UnsupportedTargetStore, safe_target


class UnsupportedTargetStoreTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "goster.sqlite3"
        self.store = UnsupportedTargetStore(
            self.path,
            database_max_bytes=4 * 1024 * 1024,
            max_rows=5,
            target_rows=3,
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_deduplicates_and_discards_query_and_fragment(self):
        self.store.record(
            "https://example.com/activity/lesson?student=alice&token=secret#answer",
            now=100,
        )
        self.store.record(
            "https://example.com/activity/lesson?student=bob&token=other",
            now=200,
        )
        targets = self.store.list_targets()
        self.assertEqual(len(targets), 1)
        self.assertEqual(targets[0]["host"], "example.com")
        self.assertEqual(targets[0]["path_hint"], "/activity/lesson")
        self.assertEqual(targets[0]["attempts"], 2)
        with sqlite3.connect(self.path) as db:
            stored = " ".join(
                str(value)
                for row in db.execute("SELECT * FROM unsupported_targets")
                for value in row
            )
        self.assertNotIn("student", stored)
        self.assertNotIn("alice", stored)
        self.assertNotIn("secret", stored)

    def test_redacts_likely_identifiers_in_path(self):
        _, _, path = safe_target(
            "https://example.com/user@example.com/12345/550e8400-e29b-41d4-a716-446655440000"
        )
        self.assertEqual(path, "/:redacted/:redacted/:redacted")

    def test_purges_by_last_seen_time(self):
        self.store.record("https://old.example/activity", now=100)
        self.store.record("https://new.example/activity", now=200)
        self.assertEqual(self.store.purge(now=250, retention_seconds=100), 1)
        self.assertEqual(self.store.list_targets()[0]["host"], "new.example")

    def test_enforces_row_quota(self):
        for number in range(10):
            self.store.record(f"https://example{number}.com/activity", now=number)
        self.assertLessEqual(len(self.store.list_targets(limit=50)), 5)


if __name__ == "__main__":
    unittest.main()
