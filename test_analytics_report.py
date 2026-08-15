#!/usr/bin/env python3

from __future__ import annotations

import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from analytics import AnalyticsStore
from analytics_report import _campaign_rows, _content_rows, _funnel_rows, _unsupported_rows
from unsupported import UnsupportedTargetStore


class AnalyticsReportTests(unittest.TestCase):
    def setUp(self):
        self.tempdir = tempfile.TemporaryDirectory()
        self.path = Path(self.tempdir.name) / "goster.sqlite3"
        self.key = "analytics-test-key-0123456789abcdef"
        self.analytics = AnalyticsStore(self.path, key=self.key)

    def tearDown(self):
        self.tempdir.cleanup()

    def test_campaign_rows_show_funnel_visitors(self):
        self.analytics.record(
            "landing_view", now=100, campaign="forum-a", visitor_ip="203.0.113.10"
        )
        self.analytics.record(
            "resolve_attempt", now=101, campaign="forum-a", visitor_ip="203.0.113.10"
        )
        self.analytics.record(
            "viewer_open", now=102, campaign="forum-a", visitor_ip="203.0.113.10"
        )
        self.assertEqual(
            _campaign_rows(self.path, since=0, excluded_tags=set()),
            [("forum-a", 1, 1, 1)],
        )

    def test_funnel_counts_only_ordered_same_visitor_day_transitions(self):
        active = "203.0.113.10"
        shared = "198.51.100.20"
        self.analytics.record("landing_view", now=100, visitor_ip=active)
        self.analytics.record("resolve_attempt", now=101, visitor_ip=active)
        self.analytics.record("resolve_success", now=102, visitor_ip=active)
        self.analytics.record("viewer_open", now=103, visitor_ip=active)
        self.analytics.record("viewer_open", now=104, visitor_ip=shared)

        self.assertEqual(
            _funnel_rows(self.path, since=0, campaign=None, excluded_tags=set()),
            {
                "landing": 1,
                "attempts": 1,
                "successes": 1,
                "viewers": 2,
                "landed_then_resolved": 1,
                "attempted_then_succeeded": 1,
                "resolved_then_viewed": 1,
            },
        )

    def test_funnel_does_not_count_reverse_order_as_conversion(self):
        visitor = "203.0.113.10"
        self.analytics.record("viewer_open", now=100, visitor_ip=visitor)
        self.analytics.record("resolve_success", now=101, visitor_ip=visitor)
        self.analytics.record("resolve_attempt", now=102, visitor_ip=visitor)
        self.analytics.record("landing_view", now=103, visitor_ip=visitor)

        rows = _funnel_rows(self.path, since=0, campaign=None, excluded_tags=set())
        self.assertEqual(rows["landed_then_resolved"], 0)
        self.assertEqual(rows["attempted_then_succeeded"], 0)
        self.assertEqual(rows["resolved_then_viewed"], 0)

    def test_content_rows_use_short_link_resolves_and_opens(self):
        with sqlite3.connect(self.path) as db:
            db.execute(
                """
                CREATE TABLE short_links (
                    code TEXT PRIMARY KEY,
                    source_url TEXT NOT NULL,
                    payload_json TEXT NOT NULL,
                    created_at INTEGER NOT NULL,
                    expires_at INTEGER NOT NULL,
                    last_accessed_at INTEGER,
                    access_count INTEGER NOT NULL DEFAULT 0
                )
                """
            )
            payload = json.dumps(
                {"title": "2. Sınıf Test", "provider": "zombify"},
                ensure_ascii=False,
            )
            db.execute(
                """
                INSERT INTO short_links (
                    code, source_url, payload_json, created_at, expires_at,
                    last_accessed_at, access_count
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    "abc346",
                    "https://www.testsaati.com/example/",
                    payload,
                    100,
                    1000,
                    120,
                    2,
                ),
            )
        rows = _content_rows(self.path, since=90, limit=20)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["provider"], "zombify")
        self.assertEqual(rows[0]["resolves"], 1)
        self.assertEqual(rows[0]["opens"], 2)
        self.assertEqual(rows[0]["last_opened"], 120)

    def test_unsupported_rows_group_real_schema_by_host(self):
        store = UnsupportedTargetStore(self.path)
        store.record("https://example.com/a", now=100)
        store.record("https://example.com/a", now=101)
        store.record("https://other.example/b", now=102)
        self.assertEqual(
            _unsupported_rows(self.path, since=90, limit=20),
            [("example.com", 2), ("other.example", 1)],
        )


if __name__ == "__main__":
    unittest.main()
