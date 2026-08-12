#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import hmac
import ipaddress
import os
import re
import sqlite3
import time

from pathlib import Path


DATABASE_PATH = Path(os.environ.get("GOSTER_DATABASE", "/var/lib/goster.me/goster.sqlite3"))
RAW_RETENTION_SECONDS = int(os.environ.get("GOSTER_ANALYTICS_RETENTION_SECONDS", str(30 * 24 * 60 * 60)))
ANALYTICS_KEY = os.environ.get("GOSTER_ANALYTICS_KEY", "")
CAMPAIGN_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
EVENTS = frozenset({
    "landing_view",
    "resolve_attempt",
    "resolve_success",
    "resolve_failure",
    "viewer_open",
    "copy_click",
    "share_click",
    "feedback_submitted",
    "about_view",
    "contact_view",
    "share_page_view",
})

# Product timeline milestones are fixed Unix timestamps so reports remain independent
# of the server timezone. 2026-08-12 14:31 Europe/Istanbul = 11:31 UTC.
MILESTONES = {
    "first-parent-whatsapp-announcement": 1786534260,
}
MILESTONE_AUDIENCE_SIZES = {
    # Parent WhatsApp group membership at announcement time, including the sender.
    "first-parent-whatsapp-announcement": 49,
}


def clean_campaign(value: str | None) -> str | None:
    candidate = (value or "").strip().lower()
    return candidate if CAMPAIGN_RE.fullmatch(candidate) else None


def daily_visitor_tag(value: str, *, occurred_at: int, key: str) -> str:
    """Return a daily rotating, keyed tag without retaining the source IP."""
    if len(key) < 32:
        raise ValueError("analytics key must be at least 32 characters")
    canonical_ip = str(ipaddress.ip_address(value))
    utc_day = time.strftime("%Y-%m-%d", time.gmtime(occurred_at))
    message = f"goster-visitor-v1\0{utc_day}\0{canonical_ip}".encode()
    return hmac.new(key.encode(), message, hashlib.sha256).hexdigest()[:32]


class AnalyticsStore:
    """Small, first-party product analytics store with rotating visitor tags."""

    def __init__(self, path: str | Path = DATABASE_PATH, *, key: str = ANALYTICS_KEY) -> None:
        self.path = Path(path)
        if key and len(key) < 32:
            raise ValueError("analytics key must be at least 32 characters")
        self.key = key
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
                    outcome TEXT,
                    visitor_tag TEXT
                )
                """
            )
            columns = {
                str(row[1]) for row in db.execute("PRAGMA table_info(analytics_events)")
            }
            if "visitor_tag" not in columns:
                db.execute("ALTER TABLE analytics_events ADD COLUMN visitor_tag TEXT")
            db.execute(
                "CREATE INDEX IF NOT EXISTS analytics_events_time_idx ON analytics_events(occurred_at)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS analytics_events_campaign_idx ON analytics_events(campaign, occurred_at)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS analytics_events_visitor_idx ON analytics_events(visitor_tag, occurred_at)"
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
               render_mode: str | None = None,
               outcome: str | None = None, visitor_ip: str | None = None) -> None:
        if event not in EVENTS:
            raise ValueError("Unsupported analytics event.")
        occurred_at = int(time.time() if now is None else now)
        visitor_tag = None
        if visitor_ip and self.key:
            visitor_tag = daily_visitor_tag(visitor_ip, occurred_at=occurred_at, key=self.key)
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO analytics_events (
                    occurred_at, event, campaign, provider, adapter, render_mode, outcome,
                    visitor_tag
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    occurred_at, event, clean_campaign(campaign),
                    self._token(provider), self._token(adapter), self._token(render_mode),
                    self._token(outcome), visitor_tag,
                ),
            )

    def purge(self, *, now: int | None = None, retention_seconds: int = RAW_RETENTION_SECONDS) -> int:
        if retention_seconds <= 0:
            raise ValueError("retention_seconds must be positive")
        cutoff = int(time.time() if now is None else now) - retention_seconds
        with self._connect() as db:
            return db.execute("DELETE FROM analytics_events WHERE occurred_at < ?", (cutoff,)).rowcount

    @staticmethod
    def _filters(*, since: int, campaign: str | None,
                 excluded_tags: set[str] | None = None) -> tuple[str, list[object]]:
        normalized = clean_campaign(campaign)
        where = "occurred_at >= ?"
        params: list[object] = [since]
        if normalized:
            where += " AND campaign = ?"
            params.append(normalized)
        tags = sorted(excluded_tags or ())
        if tags:
            where += f" AND (visitor_tag IS NULL OR visitor_tag NOT IN ({','.join('?' for _ in tags)}))"
            params.extend(tags)
        return where, params

    def summary(self, *, since: int, campaign: str | None = None,
                excluded_tags: set[str] | None = None) -> list[tuple[str, int]]:
        where, params = self._filters(
            since=since, campaign=campaign, excluded_tags=excluded_tags
        )
        query = f"SELECT event, COUNT(*) FROM analytics_events WHERE {where}"
        query += " GROUP BY event ORDER BY event"
        with self._connect() as db:
            return [(str(row[0]), int(row[1])) for row in db.execute(query, params)]

    def breakdown(self, event: str, field: str, *, since: int,
                  campaign: str | None = None,
                  excluded_tags: set[str] | None = None) -> list[tuple[str, int]]:
        if event not in EVENTS or field not in {"outcome", "provider", "render_mode"}:
            raise ValueError("unsupported analytics breakdown")
        where, params = self._filters(
            since=since, campaign=campaign, excluded_tags=excluded_tags
        )
        query = (
            f"SELECT {field}, COUNT(*) FROM analytics_events "
            f"WHERE {where} AND event = ? AND {field} IS NOT NULL "
            f"GROUP BY {field} ORDER BY COUNT(*) DESC, {field}"
        )
        params.append(event)
        with self._connect() as db:
            return [(str(row[0]), int(row[1])) for row in db.execute(query, params)]

    def visitor_stats(self, *, since: int, campaign: str | None = None,
                      excluded_tags: set[str] | None = None) -> tuple[int, int]:
        where, params = self._filters(
            since=since, campaign=campaign, excluded_tags=excluded_tags
        )
        with self._connect() as db:
            row = db.execute(
                f"SELECT COUNT(DISTINCT visitor_tag), "
                f"SUM(CASE WHEN visitor_tag IS NULL THEN 1 ELSE 0 END) "
                f"FROM analytics_events WHERE {where}",
                params,
            ).fetchone()
        return int(row[0] or 0), int(row[1] or 0)

    def event_stats(self, *, since: int, campaign: str | None = None,
                    excluded_tags: set[str] | None = None) -> list[tuple[str, int, int]]:
        where, params = self._filters(
            since=since, campaign=campaign, excluded_tags=excluded_tags
        )
        with self._connect() as db:
            return [
                (str(row[0]), int(row[1]), int(row[2]))
                for row in db.execute(
                    f"SELECT event, COUNT(*), COUNT(DISTINCT visitor_tag) "
                    f"FROM analytics_events WHERE {where} "
                    f"GROUP BY event ORDER BY event",
                    params,
                )
            ]

    def event_count(self, *, since: int, campaign: str | None = None,
                    excluded_tags: set[str] | None = None) -> int:
        where, params = self._filters(
            since=since, campaign=campaign, excluded_tags=excluded_tags
        )
        with self._connect() as db:
            return int(
                db.execute(
                    f"SELECT COUNT(*) FROM analytics_events WHERE {where}", params
                ).fetchone()[0]
            )


def tags_for_ip(value: str, *, since: int, until: int, key: str) -> set[str]:
    tags = set()
    day = since - (since % 86400)
    while day <= until:
        tags.add(daily_visitor_tag(value, occurred_at=day, key=key))
        day += 86400
    return tags


def main() -> None:
    parser = argparse.ArgumentParser(description="Privacy-focused goster.me analytics report")
    since_group = parser.add_mutually_exclusive_group()
    since_group.add_argument("--since-hours", type=int)
    since_group.add_argument("--since-milestone", choices=sorted(MILESTONES))
    parser.add_argument("--campaign")
    parser.add_argument("--exclude-ip", action="append", default=[])
    args = parser.parse_args()
    if args.since_hours is not None and args.since_hours <= 0:
        parser.error("--since-hours must be positive")

    milestone = args.since_milestone
    since_hours = 24 if args.since_hours is None and milestone is None else args.since_hours
    since = MILESTONES[milestone] if milestone else int(time.time()) - since_hours * 60 * 60

    excluded_tags: set[str] = set()
    if args.exclude_ip:
        if len(ANALYTICS_KEY) < 32:
            parser.error("--exclude-ip requires GOSTER_ANALYTICS_KEY")
        try:
            for value in args.exclude_ip:
                excluded_tags.update(
                    tags_for_ip(value, since=since, until=int(time.time()), key=ANALYTICS_KEY)
                )
        except ValueError as exc:
            parser.error(str(exc))

    store = AnalyticsStore()
    window = f"milestone={milestone}" if milestone else f"since_hours={since_hours}"
    print(f"goster.me analytics {window} campaign={clean_campaign(args.campaign) or 'all'}")
    if milestone:
        print(f"audience_size={MILESTONE_AUDIENCE_SIZES.get(milestone, 'unknown')}")
    visitor_days, untagged_events = store.visitor_stats(
        since=since, campaign=args.campaign, excluded_tags=excluded_tags
    )
    print(f"visitor_days={visitor_days} untagged_events={untagged_events}")
    if excluded_tags:
        before = store.event_count(since=since, campaign=args.campaign)
        after = store.event_count(
            since=since, campaign=args.campaign, excluded_tags=excluded_tags
        )
        print(f"excluded_events={before - after}")
    print(f"{'event':20} {'count':>7} {'visitor_days':>12}")
    for event, count, event_visitors in store.event_stats(
        since=since, campaign=args.campaign, excluded_tags=excluded_tags
    ):
        print(f"{event:20} {count:7} {event_visitors:12}")
    for title, event, field in (
        ("failure_outcomes", "resolve_failure", "outcome"),
        ("resolve_providers", "resolve_success", "provider"),
        ("viewer_providers", "viewer_open", "provider"),
        ("share_page_providers", "share_page_view", "provider"),
    ):
        rows = store.breakdown(
            event, field, since=since, campaign=args.campaign, excluded_tags=excluded_tags
        )
        if rows:
            print(f"\n{title}")
            for value, count in rows:
                print(f"{value:20} {count}")


if __name__ == "__main__":
    main()
