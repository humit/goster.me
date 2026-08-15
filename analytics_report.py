#!/usr/bin/env python3

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

import analytics


DEFAULT_LIMIT = 20


def _percent(numerator: int, denominator: int) -> str:
    if denominator <= 0:
        return "n/a"
    return f"{(100.0 * numerator / denominator):.1f}%"


def _event_map(store: analytics.AnalyticsStore, *, since: int, campaign: str | None,
               excluded_tags: set[str]) -> dict[str, tuple[int, int]]:
    return {
        event: (count, visitors)
        for event, count, visitors in store.event_stats(
            since=since,
            campaign=campaign,
            excluded_tags=excluded_tags,
        )
    }


def _content_rows(path: Path, *, since: int, limit: int) -> list[dict[str, object]]:
    with sqlite3.connect(path) as db:
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='short_links'"
        ).fetchone()
        if not exists:
            return []
        rows = db.execute(
            """
            SELECT
                source_url,
                payload_json,
                MIN(created_at) AS first_created,
                COUNT(*) AS resolves,
                SUM(access_count) AS opens,
                MAX(last_accessed_at) AS last_opened
            FROM short_links
            WHERE created_at >= ?
            GROUP BY source_url, payload_json
            ORDER BY first_created DESC
            LIMIT ?
            """,
            (since, limit),
        ).fetchall()

    result: list[dict[str, object]] = []
    for source_url, payload_json, first_created, resolves, opens, last_opened in rows:
        title = None
        provider = None
        try:
            payload = json.loads(payload_json)
            title = payload.get("title")
            provider = payload.get("provider")
        except (TypeError, ValueError):
            pass
        result.append(
            {
                "source_url": str(source_url),
                "title": title,
                "provider": provider,
                "first_created": int(first_created),
                "resolves": int(resolves or 0),
                "opens": int(opens or 0),
                "last_opened": int(last_opened) if last_opened is not None else None,
            }
        )
    return result


def _campaign_rows(path: Path, *, since: int, excluded_tags: set[str]) -> list[tuple[str, int, int, int]]:
    where = "occurred_at >= ?"
    params: list[object] = [since]
    tags = sorted(excluded_tags)
    if tags:
        where += f" AND (visitor_tag IS NULL OR visitor_tag NOT IN ({','.join('?' for _ in tags)}))"
        params.extend(tags)
    with sqlite3.connect(path) as db:
        return [
            (str(row[0]), int(row[1]), int(row[2]), int(row[3]))
            for row in db.execute(
                f"""
                SELECT
                    COALESCE(campaign, 'direct') AS source,
                    COUNT(DISTINCT CASE WHEN event = 'landing_view' THEN visitor_tag END) AS landing_visitors,
                    COUNT(DISTINCT CASE WHEN event = 'resolve_attempt' THEN visitor_tag END) AS resolving_visitors,
                    COUNT(DISTINCT CASE WHEN event = 'viewer_open' THEN visitor_tag END) AS viewer_visitors
                FROM analytics_events
                WHERE {where}
                GROUP BY COALESCE(campaign, 'direct')
                ORDER BY landing_visitors DESC, source
                """,
                params,
            )
        ]


def _unsupported_rows(path: Path, *, since: int, limit: int) -> list[tuple[str, int]]:
    with sqlite3.connect(path) as db:
        exists = db.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name='unsupported_targets'"
        ).fetchone()
        if not exists:
            return []
        columns = {row[1] for row in db.execute("PRAGMA table_info(unsupported_targets)")}
        url_column = next((name for name in ("source_url", "url") if name in columns), None)
        time_column = next((name for name in ("last_seen_at", "created_at", "occurred_at") if name in columns), None)
        count_column = next((name for name in ("attempt_count", "count") if name in columns), None)
        if not url_column or not time_column:
            return []
        count_expr = count_column if count_column else "1"
        rows = db.execute(
            f"SELECT {url_column}, {count_expr} FROM unsupported_targets WHERE {time_column} >= ?",
            (since,),
        ).fetchall()

    domains: dict[str, int] = {}
    for value, count in rows:
        hostname = (urlparse(str(value)).hostname or "unknown").lower()
        domains[hostname] = domains.get(hostname, 0) + int(count or 1)
    return sorted(domains.items(), key=lambda item: (-item[1], item[0]))[:limit]


def _format(timestamp: int, zone: ZoneInfo) -> str:
    return datetime.fromtimestamp(timestamp, zone).strftime("%Y-%m-%d %H:%M:%S %Z")


def main() -> None:
    parser = argparse.ArgumentParser(description="Operator-focused goster.me usage report")
    since_group = parser.add_mutually_exclusive_group()
    since_group.add_argument("--since-hours", type=int)
    since_group.add_argument("--since-milestone", choices=sorted(analytics.MILESTONES))
    since_group.add_argument("--since")
    parser.add_argument("--timezone", default=analytics.DEFAULT_TIMEZONE)
    parser.add_argument("--campaign")
    parser.add_argument("--exclude-ip", action="append", default=[])
    parser.add_argument("--limit", type=int, default=DEFAULT_LIMIT)
    args = parser.parse_args()

    if args.since_hours is not None and args.since_hours <= 0:
        parser.error("--since-hours must be positive")
    if args.limit <= 0 or args.limit > 100:
        parser.error("--limit must be between 1 and 100")

    try:
        zone = ZoneInfo(args.timezone)
    except Exception:
        parser.error(f"unknown timezone: {args.timezone}")

    milestone = args.since_milestone
    since_hours = 24 if args.since_hours is None and milestone is None and args.since is None else args.since_hours
    try:
        since = (
            analytics.MILESTONES[milestone]
            if milestone
            else analytics.parse_since(args.since, timezone_name=args.timezone)
            if args.since
            else int(time.time()) - since_hours * 3600
        )
    except ValueError as exc:
        parser.error(str(exc))

    now = int(time.time())
    excluded_tags: set[str] = set()
    if args.exclude_ip:
        if len(analytics.ANALYTICS_KEY) < 32:
            parser.error("--exclude-ip requires GOSTER_ANALYTICS_KEY")
        try:
            for value in args.exclude_ip:
                excluded_tags.update(
                    analytics.tags_for_ip(
                        value,
                        since=since,
                        until=now,
                        key=analytics.ANALYTICS_KEY,
                    )
                )
        except ValueError as exc:
            parser.error(str(exc))

    store = analytics.AnalyticsStore()
    campaign = analytics.clean_campaign(args.campaign)
    stats = _event_map(
        store,
        since=since,
        campaign=args.campaign,
        excluded_tags=excluded_tags,
    )

    print("goster.me usage report")
    print(f"period={_format(since, zone)} -> {_format(now, zone)}")
    print(f"campaign={campaign or 'all'}")
    if milestone:
        print(
            f"milestone={milestone} "
            f"audience_size={analytics.MILESTONE_AUDIENCE_SIZES.get(milestone, 'unknown')}"
        )

    daily_visitors, untagged = store.visitor_stats(
        since=since,
        campaign=args.campaign,
        excluded_tags=excluded_tags,
    )
    persistent, new_visitors, returning, loyal_active = store.persistent_visitor_stats(
        since=since,
        campaign=args.campaign,
        excluded_tags=excluded_tags,
    )
    print("\naudience")
    print(f"daily_visitor_tags={daily_visitors}")
    print(f"persistent_visitors={persistent}")
    print(f"new_visitors={new_visitors}")
    print(f"returning_visitors={returning}")
    print(f"returning_rate={_percent(returning, persistent)}")
    print(f"active_visitors_with_2plus_days={loyal_active}")
    print(f"untagged_events={untagged}")
    if excluded_tags:
        before = store.event_count(since=since, campaign=args.campaign)
        after = store.event_count(
            since=since,
            campaign=args.campaign,
            excluded_tags=excluded_tags,
        )
        print(f"excluded_events={before - after}")

    landing = stats.get("landing_view", (0, 0))[1]
    attempts = stats.get("resolve_attempt", (0, 0))[1]
    successes = stats.get("resolve_success", (0, 0))[1]
    viewers = stats.get("viewer_open", (0, 0))[1]
    print("\nfunnel")
    print(f"landing_visitors={landing}")
    print(f"resolve_visitors={attempts} activation={_percent(attempts, landing)}")
    print(f"successful_resolve_visitors={successes} success={_percent(successes, attempts)}")
    print(f"viewer_visitors={viewers} view_after_resolve={_percent(viewers, successes)}")

    print(f"\n{'event':20} {'count':>7} {'visitor_days':>12}")
    for event, count, event_visitors in store.event_stats(
        since=since,
        campaign=args.campaign,
        excluded_tags=excluded_tags,
    ):
        print(f"{event:20} {count:7} {event_visitors:12}")

    campaigns = _campaign_rows(store.path, since=since, excluded_tags=excluded_tags)
    if campaigns and args.campaign is None:
        print("\ncampaigns")
        print(f"{'source':24} {'landing':>7} {'resolve':>7} {'viewer':>7}")
        for source, landing_count, resolve_count, viewer_count in campaigns:
            print(f"{source:24.24} {landing_count:7} {resolve_count:7} {viewer_count:7}")

    content = _content_rows(store.path, since=since, limit=args.limit)
    if content:
        print("\nrecent_content")
        if args.exclude_ip or args.campaign:
            print("note=content rows come from short_links and are not visitor/campaign filtered yet")
        for row in content:
            label = row["title"] or row["source_url"]
            last_open = (
                _format(int(row["last_opened"]), zone)
                if row["last_opened"] is not None
                else "never"
            )
            print(
                f"provider={row['provider'] or 'unknown'} resolves={row['resolves']} "
                f"opens={row['opens']} first={_format(int(row['first_created']), zone)} "
                f"last_open={last_open}"
            )
            print(f"  {label}")
            print(f"  {row['source_url']}")

    unsupported = _unsupported_rows(store.path, since=since, limit=args.limit)
    if unsupported:
        print("\nunsupported_demand")
        for domain, count in unsupported:
            print(f"{domain:40.40} {count}")

    for title, event, field in (
        ("failure_outcomes", "resolve_failure", "outcome"),
        ("resolve_providers", "resolve_success", "provider"),
        ("viewer_providers", "viewer_open", "provider"),
        ("share_page_providers", "share_page_view", "provider"),
    ):
        rows = store.breakdown(
            event,
            field,
            since=since,
            campaign=args.campaign,
            excluded_tags=excluded_tags,
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
