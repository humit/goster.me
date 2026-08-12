#!/usr/bin/env python3

from __future__ import annotations

import tempfile
import unittest

from pathlib import Path
from unittest.mock import patch

from feedback import FeedbackStore
from feedback_telegram import SAFE_TEXT_LIMIT, format_notification, notify_pending


class FeedbackTelegramTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "goster.sqlite3"
        self.store = FeedbackStore(
            self.path,
            database_max_bytes=4 * 1024 * 1024,
            max_rows=20,
            target_rows=15,
        )

    def tearDown(self):
        self.tempdir.cleanup()

    def test_successful_delivery_is_not_repeated(self):
        self.store.submit("problem", "Etkinlik açılmadı.", now=100)
        with patch("feedback_telegram.send_message") as send:
            self.assertEqual(notify_pending(self.store, token="token", chat_id="123"), 1)
            self.assertEqual(notify_pending(self.store, token="token", chat_id="123"), 0)
        send.assert_called_once()

    def test_failed_delivery_remains_pending(self):
        self.store.submit("suggestion", "Yeni site desteği.", now=100)
        with patch("feedback_telegram.send_message", side_effect=RuntimeError("network")):
            with self.assertRaises(RuntimeError):
                notify_pending(self.store, token="token", chat_id="123")
        self.assertEqual(len(self.store.pending_notifications()), 1)

    def test_long_message_is_truncated_with_recovery_hint(self):
        text = format_notification({
            "id": "abcdef123456", "created_at": 100,
            "category": "problem", "message": "x" * 5000,
        })
        self.assertLessEqual(len(text), SAFE_TEXT_LIMIT)
        self.assertIn("Mesaj kısaltıldı", text)
        self.assertIn("tools/goster feedback list", text)


if __name__ == "__main__":
    unittest.main()
