#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest

from pathlib import Path

from feedback import FeedbackStore, normalize_submission


class FeedbackStoreTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "goster.sqlite3"
        self.store = FeedbackStore(
            self.path,
            database_max_bytes=4 * 1024 * 1024,
            max_rows=5,
            target_rows=3,
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_submission_stores_no_visitor_identifier(self):
        receipt = self.store.submit("suggestion", "Daha büyük bir düğme olabilir.", now=100)
        messages = self.store.list_messages()
        self.assertEqual(messages[0]["id"], receipt)
        self.assertEqual(messages[0]["category"], "suggestion")
        self.assertEqual(messages[0]["status"], "unread")

        with self.store._connect() as db:
            columns = [row[1] for row in db.execute("PRAGMA table_info(feedback_messages)")]
        self.assertNotIn("ip", columns)
        self.assertNotIn("user_agent", columns)
        self.assertNotIn("email", columns)
        self.assertNotIn("phone", columns)

    def test_rejects_spam_trap_and_invalid_content(self):
        with self.assertRaises(ValueError):
            normalize_submission("problem", "Gerçek mesaj", "https://spam.example")
        with self.assertRaises(ValueError):
            normalize_submission("unknown", "Gerçek mesaj")
        with self.assertRaises(ValueError):
            normalize_submission("problem", "x")
        with self.assertRaises(ValueError):
            normalize_submission("problem", "ok\x00bad")

    def test_marks_message_reviewed(self):
        receipt = self.store.submit("problem", "Bir şey çalışmadı.", now=100)
        self.assertTrue(self.store.mark_reviewed(receipt, now=200))
        reviewed = self.store.list_messages(status="reviewed")
        self.assertEqual(reviewed[0]["reviewed_at"], 200)
        self.assertFalse(self.store.mark_reviewed("not-a-receipt"))

    def test_enforces_row_quota(self):
        for timestamp in range(10):
            self.store.submit("other", f"Mesaj {timestamp}", now=timestamp)
        self.assertLessEqual(len(self.store.list_messages(status="all", limit=50)), 5)

    def test_purges_expired_messages(self):
        self.store.submit("problem", "Eski mesaj", now=100)
        self.store.submit("problem", "Yeni mesaj", now=200)
        self.assertEqual(self.store.purge(now=250, retention_seconds=100), 1)
        self.assertEqual(len(self.store.list_messages(status="all")), 1)


if __name__ == "__main__":
    unittest.main()
