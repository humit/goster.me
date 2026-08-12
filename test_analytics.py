#!/usr/bin/env python3

from __future__ import annotations

import sqlite3
import tempfile
import unittest

from pathlib import Path

from analytics import (
    AnalyticsStore,
    MILESTONES,
    MILESTONE_AUDIENCE_SIZES,
    clean_campaign,
    daily_visitor_tag,
    tags_for_ip,
)


class AnalyticsStoreTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "goster.sqlite3"
        self.key = "analytics-test-key-0123456789abcdef"
        self.store = AnalyticsStore(self.path, key=self.key)

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
        self.assertIn("visitor_tag", columns)
        self.assertEqual(row, ("resolve_success", "veli-whatsapp-2026-08", "youtube"))

    def test_daily_visitor_tag_is_stable_within_day_and_rotates(self):
        first = daily_visitor_tag("203.0.113.10", occurred_at=100, key=self.key)
        same_day = daily_visitor_tag("203.0.113.10", occurred_at=200, key=self.key)
        next_day = daily_visitor_tag("203.0.113.10", occurred_at=86401, key=self.key)
        self.assertEqual(first, same_day)
        self.assertNotEqual(first, next_day)
        self.assertNotIn("203.0.113.10", first)

    def test_rejects_short_configured_key(self):
        with self.assertRaises(ValueError):
            AnalyticsStore(self.path, key="too-short")

    def test_excludes_ip_without_storing_raw_address(self):
        self.store.record("landing_view", now=100, visitor_ip="203.0.113.10")
        self.store.record("landing_view", now=100, visitor_ip="198.51.100.20")
        excluded = tags_for_ip(
            "203.0.113.10", since=0, until=200, key=self.key
        )
        self.assertEqual(
            self.store.summary(since=0, excluded_tags=excluded),
            [("landing_view", 1)],
        )
        with sqlite3.connect(self.path) as db:
            stored = " ".join(
                str(value)
                for row in db.execute("SELECT * FROM analytics_events")
                for value in row
            )
        self.assertNotIn("203.0.113.10", stored)
        self.assertNotIn("198.51.100.20", stored)

    def test_event_stats_include_daily_visitor_counts(self):
        self.store.record("landing_view", now=100, visitor_ip="203.0.113.10")
        self.store.record("landing_view", now=101, visitor_ip="203.0.113.10")
        self.store.record("landing_view", now=102, visitor_ip="198.51.100.20")
        self.assertEqual(
            self.store.event_stats(since=0),
            [("landing_view", 3, 2)],
        )

    def test_migrates_existing_analytics_table(self):
        legacy_path = Path(self.tempdir.name) / "legacy.sqlite3"
        with sqlite3.connect(legacy_path) as db:
            db.execute(
                """
                CREATE TABLE analytics_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    occurred_at INTEGER NOT NULL,
                    event TEXT NOT NULL,
                    campaign TEXT,
                    provider TEXT,
                    adapter TEXT,
                    render_mode TEXT,
                    outcome TEXT
                )
                """
            )
        AnalyticsStore(legacy_path, key=self.key)
        with sqlite3.connect(legacy_path) as db:
            columns = [row[1] for row in db.execute("PRAGMA table_info(analytics_events)")]
        self.assertIn("visitor_tag", columns)

    def test_rejects_unknown_event(self):
        with self.assertRaises(ValueError):
            self.store.record("page_view")

    def test_accepts_anonymous_feedback_event(self):
        self.store.record("feedback_submitted", now=100)
        self.assertEqual(self.store.summary(since=0), [("feedback_submitted", 1)])

    def test_accepts_information_page_views(self):
        self.store.record("about_view", now=100)
        self.store.record("contact_view", now=100)
        self.store.record("share_page_view", now=100)
        self.assertEqual(
            self.store.summary(since=0),
            [("about_view", 1), ("contact_view", 1), ("share_page_view", 1)],
        )

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
