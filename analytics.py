#!/usr/bin/env python3

from __future__ import annotations

import argparse
import os
import re
import sqlite3
import time

from pathlib import Path


DATABASE_PATH = Path(os.environ.get("GOSTER_DATABASE", "/var/lib/goster.me/goster.sqlite3"))
RAW_RETENTION_SECONDS = int(os.environ.get("GOSTER_ANALYTICS_RETENTION_SECONDS", str(30 * 24 * 60 * 60)))
CAMPAIGN_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
CODE_RE = re.compile(r"^[a-z0-9]{4,16}$")
EVENTS = frozenset({
    "landing_view",
    "resolve_attempt",
    "resolve_success",
    "resolve_failure",
    "viewer_open",
    "copy_click",
    "share_click",
})


def clean_campaign(value: str | None) -> str | None:
    candidate = (value or "").strip().lower()
    return candidate if CAMPAIGN_RE.fullmatch(candidate) else None


class AnalyticsStore:
    """Small, first-party product analytics store with no visitor identifiers."""

    def __init__(self, path: str | Path = DATABASE_PATH) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as db:
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS analytics_events (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    occurred_at INTEGER NOT NULL,
                    event TEXT NOT NULL,
                    campaign TEXT,
                    provider TEXT,
                    adapter TEXT,
                    render_mode TEXT,
                    code TEXT,
                    outcome TEXT
                )
                """
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS analytics_events_time_idx ON analytics_events(occurred_at)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS analytics_events_campaign_idx ON analytics_events(campaign, occurred_at)"
            )

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.path, timeout=10)

    @staticmethod
    def _token(value: str | None, maximum: int = 64) -> str | None:
        if value is None:
            return None
        value = value.strip().lower()
        if not value or len(value) > maximum or not re.fullmatch(r"[a-z0-9_-]+", value):
            return None
        return value

    def record(self, event: str, *, now: int | None = None, campaign: str | None = None,
               provider: str | None = None, adapter: str | None = None,
               render_mode: str | None = None, code: str | None = None,
               outcome: str | None = None) -> None:
        if event not in EVENTS:
            raise ValueError("Unsupported analytics event.")
        normalized_code = (code or "").strip().lower() or None
        if normalized_code is not None and not CODE_RE.fullmatch(normalized_code):
            raise ValueError("Invalid analytics code.")
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO analytics_events (
                    occurred_at, event, campaign, provider, adapter, render_mode, code, outcome
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    int(time.time() if now is None else now), event, clean_campaign(campaign),
                    self._token(provider), self._token(adapter), self._token(render_mode),
                    normalized_code, self._token(outcome),
                ),
            )

    def purge(self, *, now: int | None = None, retention_seconds: int = RAW_RETENTION_SECONDS) -> int:
        if retention_seconds <= 0:
            raise ValueError("retention_seconds must be positive")
        cutoff = int(time.time() if now is None else now) - retention_seconds
        with self._connect() as db:
            return db.execute("DELETE FROM analytics_events WHERE occurred_at < ?", (cutoff,)).rowcount

    def summary(self, *, since: int, campaign: str | None = None) -> list[tuple[str, int]]:
        normalized = clean_campaign(campaign)
        query = "SELECT event, COUNT(*) FROM analytics_events WHERE occurred_at >= ?"
        params: list[object] = [since]
        if normalized:
            query += " AND campaign = ?"
            params.append(normalized)
        query += " GROUP BY event ORDER BY event"
        with self._connect() as db:
            return [(str(row[0]), int(row[1])) for row in db.execute(query, params)]


def main() -> None:
    parser = argparse.ArgumentParser(description="Privacy-focused goster.me analytics report")
    parser.add_argument("--since-hours", type=int, default=24)
    parser.add_argument("--campaign")
    args = parser.parse_args()
    if args.since_hours <= 0:
        parser.error("--since-hours must be positive")
    store = AnalyticsStore()
    since = int(time.time()) - args.since_hours * 60 * 60
    print(f"goster.me analytics since_hours={args.since_hours} campaign={clean_campaign(args.campaign) or 'all'}")
    for event, count in store.summary(since=since, campaign=args.campaign):
        print(f"{event:20} {count}")


if __name__ == "__main__":
    main()
