#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import hmac
import ipaddress
import json
import os
import re
import sqlite3
import time

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo


DATABASE_PATH = Path(os.environ.get("GOSTER_DATABASE", "/var/lib/goster.me/goster.sqlite3"))
RAW_RETENTION_SECONDS = int(os.environ.get("GOSTER_ANALYTICS_RETENTION_SECONDS", str(30 * 24 * 60 * 60)))
ANALYTICS_KEY = os.environ.get("GOSTER_ANALYTICS_KEY", "")
DEFAULT_TIMEZONE = os.environ.get("GOSTER_ANALYTICS_TIMEZONE", "Europe/Istanbul")
CAMPAIGN_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,63}$")
VISITOR_ID_RE = re.compile(r"^[A-Za-z0-9_-]{20,64}$")
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


def clean_visitor_id(value: str | None) -> str | None:
    candidate = (value or "").strip()
    return candidate if VISITOR_ID_RE.fullmatch(candidate) else None


def daily_visitor_tag(value: str, *, occurred_at: int, key: str) -> str:
    """Return a daily rotating, keyed tag without retaining the source IP."""
    if len(key) < 32:
        raise ValueError("analytics key must be at least 32 characters")
    canonical_ip = str(ipaddress.ip_address(value))
    utc_day = time.strftime("%Y-%m-%d", time.gmtime(occurred_at))
    message = f"goster-visitor-v1\0{utc_day}\0{canonical_ip}".encode()
    return hmac.new(key.encode(), message, hashlib.sha256).hexdigest()[:32]


def persistent_visitor_tag(value: str, *, key: str) -> str:
    """Return a stable keyed network tag without retaining the source IP."""
    if len(key) < 32:
        raise ValueError("analytics key must be at least 32 characters")
    canonical_ip = str(ipaddress.ip_address(value))
    message = f"goster-persistent-visitor-v1\0{canonical_ip}".encode()
    return hmac.new(key.encode(), message, hashlib.sha256).hexdigest()[:32]


class AnalyticsStore:
    """Small, first-party product analytics store with privacy-preserving identity."""

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
                    visitor_tag TEXT,
                    visitor_id TEXT,
                    content_ref TEXT
                )
                """
            )
            columns = {
                str(row[1]) for row in db.execute("PRAGMA table_info(analytics_events)")
            }
            if "visitor_tag" not in columns:
                db.execute("ALTER TABLE analytics_events ADD COLUMN visitor_tag TEXT")
            if "visitor_id" not in columns:
                db.execute("ALTER TABLE analytics_events ADD COLUMN visitor_id TEXT")
            if "content_ref" not in columns:
                db.execute("ALTER TABLE analytics_events ADD COLUMN content_ref TEXT")
            db.execute(
                """
                CREATE TABLE IF NOT EXISTS analytics_visitors (
                    visitor_id TEXT PRIMARY KEY,
                    first_seen INTEGER NOT NULL,
                    last_seen INTEGER NOT NULL,
                    active_days INTEGER NOT NULL,
                    last_active_day TEXT NOT NULL
                )
                """
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS analytics_events_time_idx ON analytics_events(occurred_at)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS analytics_events_campaign_idx ON analytics_events(campaign, occurred_at)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS analytics_events_visitor_idx ON analytics_events(visitor_tag, occurred_at)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS analytics_events_persistent_visitor_idx ON analytics_events(visitor_id, occurred_at)"
            )
            db.execute(
                "CREATE INDEX IF NOT EXISTS analytics_events_content_idx ON analytics_events(content_ref, occurred_at)"
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

    @staticmethod
    def _active_day(occurred_at: int) -> str:
        return time.strftime("%Y-%m-%d", time.gmtime(occurred_at))

    def record(self, event: str, *, now: int | None = None, campaign: str | None = None,
               provider: str | None = None, adapter: str | None = None,
               render_mode: str | None = None, outcome: str | None = None,
               visitor_ip: str | None = None, visitor_id: str | None = None,
               content_ref: str | None = None) -> None:
        if event not in EVENTS:
            raise ValueError("Unsupported analytics event.")
        occurred_at = int(time.time() if now is None else now)
        visitor_tag = None
        persistent_id = clean_visitor_id(visitor_id)
        if visitor_ip and self.key:
            visitor_tag = daily_visitor_tag(visitor_ip, occurred_at=occurred_at, key=self.key)
            if persistent_id is None:
                persistent_id = persistent_visitor_tag(visitor_ip, key=self.key)
        normalized_content_ref = self._token(content_ref)
        active_day = self._active_day(occurred_at)
        with self._connect() as db:
            db.execute(
                """
                INSERT INTO analytics_events (
                    occurred_at, event, campaign, provider, adapter, render_mode, outcome,
                    visitor_tag, visitor_id, content_ref
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    occurred_at, event, clean_campaign(campaign),
                    self._token(provider), self._token(adapter), self._token(render_mode),
                    self._token(outcome), visitor_tag, persistent_id, normalized_content_ref,
                ),
            )
            if persistent_id:
                db.execute(
                    """
                    INSERT INTO analytics_visitors (
                        visitor_id, first_seen, last_seen, active_days, last_active_day
                    ) VALUES (?, ?, ?, 1, ?)
                    ON CONFLICT(visitor_id) DO UPDATE SET
                        first_seen = MIN(analytics_visitors.first_seen, excluded.first_seen),
                        last_seen = MAX(analytics_visitors.last_seen, excluded.last_seen),
                        active_days = analytics_visitors.active_days +
                            CASE WHEN analytics_visitors.last_active_day <> excluded.last_active_day
                                 THEN 1 ELSE 0 END,
                        last_active_day = MAX(
                            analytics_visitors.last_active_day, excluded.last_active_day
                        )
                    """,
                    (persistent_id, occurred_at, occurred_at, active_day),
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

    def persistent_visitor_stats(self, *, since: int, campaign: str | None = None,
                                 excluded_tags: set[str] | None = None) -> tuple[int, int, int, int]:
        where, params = self._filters(
            since=since, campaign=campaign, excluded_tags=excluded_tags
        )
        with self._connect() as db:
            row = db.execute(
                f"""
                WITH active AS (
                    SELECT DISTINCT visitor_id
                    FROM analytics_events
                    WHERE {where} AND visitor_id IS NOT NULL
                )
                SELECT
                    COUNT(*),
                    SUM(CASE WHEN v.first_seen >= ? THEN 1 ELSE 0 END),
                    SUM(CASE WHEN v.first_seen < ? THEN 1 ELSE 0 END),
                    SUM(CASE WHEN v.active_days >= 2 THEN 1 ELSE 0 END)
                FROM active a
                JOIN analytics_visitors v ON v.visitor_id = a.visitor_id
                """,
                [*params, since, since],
            ).fetchone()
        return tuple(int(value or 0) for value in row)

    def loyalty_distribution(self) -> list[tuple[str, int]]:
        with self._connect() as db:
            row = db.execute(
                """
                SELECT
                    SUM(CASE WHEN active_days >= 2 THEN 1 ELSE 0 END),
                    SUM(CASE WHEN active_days >= 3 THEN 1 ELSE 0 END),
                    SUM(CASE WHEN active_days >= 5 THEN 1 ELSE 0 END)
                FROM analytics_visitors
                """
            ).fetchone()
        return [
            ("2+ days", int(row[0] or 0)),
            ("3+ days", int(row[1] or 0)),
            ("5+ days", int(row[2] or 0)),
        ]

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

    def content_activity(self, *, since: int, campaign: str | None = None,
                         excluded_tags: set[str] | None = None) -> list[dict[str, object]]:
        where, params = self._filters(
            since=since, campaign=campaign, excluded_tags=excluded_tags
        )
        with self._connect() as db:
            has_short_links = db.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='short_links'"
            ).fetchone()
            if not has_short_links:
                return []
            rows = db.execute(
                f"""
                SELECT
                    e.content_ref,
                    s.source_url,
                    s.payload_json,
                    MIN(e.occurred_at),
                    SUM(CASE WHEN e.event = 'resolve_success' THEN 1 ELSE 0 END),
                    SUM(CASE WHEN e.event = 'viewer_open' THEN 1 ELSE 0 END),
                    COUNT(DISTINCT CASE WHEN e.event = 'viewer_open' THEN e.visitor_id END)
                FROM analytics_events e
                LEFT JOIN short_links s ON s.code = e.content_ref
                WHERE {where} AND e.content_ref IS NOT NULL
                GROUP BY e.content_ref, s.source_url, s.payload_json
                ORDER BY MIN(e.occurred_at) DESC
                """,
                params,
            ).fetchall()
        result = []
        for code, source_url, payload_json, first_seen, resolves, opens, viewers in rows:
            title = None
            provider = None
            if payload_json:
                try:
                    payload = json.loads(payload_json)
                    title = payload.get("title")
                    provider = payload.get("provider")
                except (TypeError, ValueError):
                    pass
            result.append({
                "code": str(code),
                "source_url": source_url,
                "title": title,
                "provider": provider,
                "first_seen": int(first_seen),
                "resolves": int(resolves or 0),
                "opens": int(opens or 0),
                "viewers": int(viewers or 0),
            })
        return result


def tags_for_ip(value: str, *, since: int, until: int, key: str) -> set[str]:
    tags = set()
    day = since - (since % 86400)
    while day <= until:
        tags.add(daily_visitor_tag(value, occurred_at=day, key=key))
        day += 86400
    return tags


def parse_since(value: str, *, timezone_name: str) -> int:
    try:
        zone = ZoneInfo(timezone_name)
    except Exception as exc:
        raise ValueError(f"unknown timezone: {timezone_name}") from exc
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError as exc:
        raise ValueError("--since must be an ISO date/time, e.g. 2026-08-15T13:15") from exc
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=zone)
    return int(parsed.timestamp())


def format_local(timestamp: int, timezone_name: str) -> str:
    return datetime.fromtimestamp(timestamp, ZoneInfo(timezone_name)).strftime("%Y-%m-%d %H:%M:%S %Z")


def main() -> None:
    parser = argparse.ArgumentParser(description="Privacy-focused goster.me analytics report")
    since_group = parser.add_mutually_exclusive_group()
    since_group.add_argument("--since-hours", type=int)
    since_group.add_argument("--since-milestone", choices=sorted(MILESTONES))
    since_group.add_argument("--since")
    parser.add_argument("--timezone", default=DEFAULT_TIMEZONE)
    parser.add_argument("--campaign")
    parser.add_argument("--exclude-ip", action="append", default=[])
    args = parser.parse_args()
    if args.since_hours is not None and args.since_hours <= 0:
        parser.error("--since-hours must be positive")

    milestone = args.since_milestone
    since_hours = 24 if args.since_hours is None and milestone is None and args.since is None else args.since_hours
    try:
        since = (
            MILESTONES[milestone] if milestone
            else parse_since(args.since, timezone_name=args.timezone) if args.since
            else int(time.time()) - since_hours * 60 * 60
        )
        ZoneInfo(args.timezone)
    except ValueError as exc:
        parser.error(str(exc))

    now = int(time.time())
    excluded_tags: set[str] = set()
    if args.exclude_ip:
        if len(ANALYTICS_KEY) < 32:
            parser.error("--exclude-ip requires GOSTER_ANALYTICS_KEY")
        try:
            for value in args.exclude_ip:
                excluded_tags.update(
                    tags_for_ip(value, since=since, until=now, key=ANALYTICS_KEY)
                )
        except ValueError as exc:
            parser.error(str(exc))

    store = AnalyticsStore()
    print("goster.me usage report")
    print(f"period={format_local(since, args.timezone)} -> {format_local(now, args.timezone)}")
    print(f"campaign={clean_campaign(args.campaign) or 'all'}")
    if milestone:
        print(f"milestone={milestone} audience_size={MILESTONE_AUDIENCE_SIZES.get(milestone, 'unknown')}")

    visitor_days, untagged_events = store.visitor_stats(
        since=since, campaign=args.campaign, excluded_tags=excluded_tags
    )
    persistent, new_visitors, returning, loyal_active = store.persistent_visitor_stats(
        since=since, campaign=args.campaign, excluded_tags=excluded_tags
    )
    print("\naudience")
    print(f"daily_visitor_tags={visitor_days}")
    print(f"persistent_visitors={persistent}")
    print(f"new_visitors={new_visitors}")
    print(f"returning_visitors={returning}")
    print(f"active_visitors_with_2plus_days={loyal_active}")
    print(f"untagged_events={untagged_events}")
    if excluded_tags:
        before = store.event_count(since=since, campaign=args.campaign)
        after = store.event_count(
            since=since, campaign=args.campaign, excluded_tags=excluded_tags
        )
        print(f"excluded_events={before - after}")

    print(f"\n{'event':20} {'count':>7} {'visitor_days':>12}")
    for event, count, event_visitors in store.event_stats(
        since=since, campaign=args.campaign, excluded_tags=excluded_tags
    ):
        print(f"{event:20} {count:7} {event_visitors:12}")

    activity = store.content_activity(
        since=since, campaign=args.campaign, excluded_tags=excluded_tags
    )
    if activity:
        print("\nrecent_content")
        for row in activity:
            label = row["title"] or row["source_url"] or row["code"]
            print(
                f"{row['code']} provider={row['provider'] or 'unknown'} "
                f"resolves={row['resolves']} viewers={row['viewers']} opens={row['opens']} "
                f"first={format_local(int(row['first_seen']), args.timezone)}"
            )
            print(f"  {label}")

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

    print("\nloyalty_all_time")
    for label, count in store.loyalty_distribution():
        print(f"{label:10} {count}")


if __name__ == "__main__":
    main()
