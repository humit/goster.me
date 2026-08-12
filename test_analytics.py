#!/usr/bin/env python3

from __future__ import annotations

import sqlite3
import tempfile
import unittest

from pathlib import Path

from analytics import AnalyticsStore, MILESTONES, MILESTONE_AUDIENCE_SIZES, clean_campaign


class AnalyticsStoreTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "goster.sqlite3"
        self.store = AnalyticsStore(self.path)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_stores_only_allowlisted_product_fields(self):
        self.store.record(
            "resolve_success", now=100, campaign="veli-whatsapp-2026-08",
            provider="youtube", adapter="youtube", render_mode="youtube-embed",
        )
        with sqlite3.connect(self.path) as db:
            columns = [row[1] for row in db.execute("PRAGMA table_info(analytics_events)")]
            row = db.execute("SELECT event, campaign, provider FROM analytics_events").fetchone()
        self.assertNotIn("ip", columns)
        self.assertNotIn("user_agent", columns)
        self.assertNotIn("url", columns)
        self.assertNotIn("code", columns)
        self.assertEqual(row, ("resolve_success", "veli-whatsapp-2026-08", "youtube"))

    def test_rejects_unknown_event(self):
        with self.assertRaises(ValueError):
            self.store.record("page_view")

    def test_invalid_campaign_is_discarded(self):
        self.assertIsNone(clean_campaign("parent@example.com"))
        self.assertEqual(clean_campaign("Veli-WhatsApp-2026-08"), "veli-whatsapp-2026-08")

    def test_first_parent_announcement_milestone_is_stable(self):
        self.assertEqual(MILESTONES["first-parent-whatsapp-announcement"], 1786534260)
        self.assertEqual(MILESTONE_AUDIENCE_SIZES["first-parent-whatsapp-announcement"], 49)

    def test_purge_removes_only_expired_raw_events(self):
        self.store.record("landing_view", now=100)
        self.store.record("landing_view", now=200)
        self.assertEqual(self.store.purge(now=250, retention_seconds=100), 1)
        self.assertEqual(self.store.summary(since=0), [("landing_view", 1)])


if __name__ == "__main__":
    unittest.main()
