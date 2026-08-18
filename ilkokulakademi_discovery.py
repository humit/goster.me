#!/usr/bin/env python3

from __future__ import annotations

import argparse
import re
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

from adapters import (
    AdapterError,
    ResolveError,
    UnsupportedURL,
    fetch_html,
    matching_adapters,
    resolve_url,
)


SITE_ROOT = "https://www.ilkokulakademi.com/"
INDEX_URL = urljoin(SITE_ROOT, "search?max-results=50")
ALLOWED_HOSTS = {
    "ilkokulakademi.com",
    "www.ilkokulakademi.com",
}
POST_PATH_RE = re.compile(r"^/\d{4}/\d{2}/[^?#]+\.html$")
GAMEISH_RE = re.compile(
    r"(game|quiz|question|answer|score|result|option|exam|test|start|finish|oyun|soru|cevap|sonuc)",
    re.IGNORECASE,
)


class DiscoveryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.classes: set[str] = set()
        self.links: list[str] = []
        self.iframes: list[str] = []

    def handle_starttag(self, tag: str, attrs) -> None:
        values = dict(attrs)
        tag = tag.lower()

        element_id = values.get("id")
        if element_id:
            self.ids.add(element_id)

        for value in (values.get("class") or "").split():
            if value:
                self.classes.add(value)

        if tag == "a":
            href = values.get("href")
            if href:
                self.links.append(href)

        if tag == "iframe":
            src = (
                values.get("src")
                or values.get("data-src")
                or values.get("data-lazy-src")
            )
            if src:
                self.iframes.append(src)


def hostname(url: str) -> str:
    return (urlparse(url).hostname or "").lower()


def parse_html(value: str) -> DiscoveryParser:
    parser = DiscoveryParser()
    parser.feed(value)
    return parser


def discover_post_urls(
    index_html: str,
    *,
    base_url: str = INDEX_URL,
) -> list[str]:
    parser = parse_html(index_html)
    urls: list[str] = []

    for href in parser.links:
        url = urljoin(base_url, href)
        parsed = urlparse(url)

        if hostname(url) not in ALLOWED_HOSTS:
            continue

        if not POST_PATH_RE.match(parsed.path):
            continue

        canonical = parsed._replace(
            query="",
            fragment="",
        ).geturl()

        urls.append(canonical)

    return list(dict.fromkeys(urls))


def discovery_fingerprint(html: str, *, base_url: str) -> tuple[str, ...]:
    parser = parse_html(html)

    ids = sorted(
        value for value in parser.ids
        if GAMEISH_RE.search(value)
    )
    classes = sorted(
        value for value in parser.classes
        if GAMEISH_RE.search(value)
    )
    iframe_hosts = sorted({
        hostname(urljoin(base_url, src))
        for src in parser.iframes
        if hostname(urljoin(base_url, src))
    })

    parts = [
        *(f"id:{value}" for value in ids),
        *(f"class:{value}" for value in classes),
        *(f"iframe:{value}" for value in iframe_hosts),
    ]

    return tuple(parts) or ("no-gameish-fingerprint",)


@dataclass(frozen=True)
class DiscoveryRecord:
    url: str
    status: str
    adapter: str | None
    selector: str | None
    reason: str | None
    fingerprint: tuple[str, ...]


def inspect_url(url: str) -> DiscoveryRecord:
    candidates = matching_adapters(url)
    status = "resolved"
    adapter = None
    selector = None
    reason = None

    try:
        result = resolve_url(url)
        adapter = result.adapter
        selector = result.selector

    except UnsupportedURL as exc:
        status = "known-unresolved" if candidates else "unsupported"
        reason = str(exc)

    except (ResolveError, AdapterError) as exc:
        status = "error"
        reason = str(exc)

    fingerprint = ("not-inspected",)

    try:
        final_url, html = fetch_html(
            url,
            allowed_hosts=ALLOWED_HOSTS,
        )
        fingerprint = discovery_fingerprint(
            html,
            base_url=final_url,
        )
    except (ResolveError, UnsupportedURL):
        pass

    return DiscoveryRecord(
        url=url,
        status=status,
        adapter=adapter,
        selector=selector,
        reason=reason,
        fingerprint=fingerprint,
    )


def scan(
    *,
    index_url: str = INDEX_URL,
    limit: int = 0,
    delay_ms: int = 250,
) -> list[DiscoveryRecord]:
    final_url, index_html = fetch_html(
        index_url,
        allowed_hosts=ALLOWED_HOSTS,
    )
    urls = discover_post_urls(
        index_html,
        base_url=final_url,
    )

    if limit > 0:
        urls = urls[:limit]

    records: list[DiscoveryRecord] = []

    for index, url in enumerate(urls, 1):
        print(
            f"[{index}/{len(urls)}] {url}",
            flush=True,
        )
        records.append(inspect_url(url))

        if delay_ms > 0 and index < len(urls):
            time.sleep(delay_ms / 1000.0)

    return records


def print_report(records: list[DiscoveryRecord]) -> None:
    counts = Counter(record.status for record in records)

    print()
    print("===== SUMMARY =====")
    print(f"URLs scanned       : {len(records)}")

    for status in (
        "resolved",
        "known-unresolved",
        "unsupported",
        "error",
    ):
        print(f"{status:18}: {counts[status]}")

    adapters = Counter(
        record.adapter
        for record in records
        if record.status == "resolved" and record.adapter
    )

    print()
    print("===== RESOLVED ADAPTERS =====")
    for adapter, count in adapters.most_common():
        print(f"{count:5}  {adapter}")

    clusters: dict[tuple[str, ...], list[DiscoveryRecord]] = defaultdict(list)

    for record in records:
        if record.status == "known-unresolved":
            clusters[record.fingerprint].append(record)

    print()
    print("===== UNRESOLVED FINGERPRINT CLUSTERS =====")

    if not clusters:
        print("none")
        return

    ordered = sorted(
        clusters.items(),
        key=lambda item: (-len(item[1]), item[0]),
    )

    for index, (fingerprint, members) in enumerate(ordered, 1):
        print(f"cluster {index}: {len(members)} URL(s)")
        print("    fingerprint: " + ", ".join(fingerprint[:20]))
        if len(fingerprint) > 20:
            print(f"    ... +{len(fingerprint) - 20} more")

        for member in members[:3]:
            print(f"    example: {member.url}")

        if members[0].reason:
            print(f"    reason : {members[0].reason}")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Discover İlkokul Akademi post URLs and report current adapter "
            "coverage plus unresolved DOM fingerprint clusters."
        )
    )
    parser.add_argument(
        "--index-url",
        default=INDEX_URL,
        help=f"Blogger search/index page (default: {INDEX_URL})",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=0,
        help="Scan at most N discovered posts; 0 means all discovered on the index page.",
    )
    parser.add_argument(
        "--delay-ms",
        type=int,
        default=250,
        help="Delay between post inspections (default: 250 ms).",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.limit < 0:
        raise SystemExit("ERROR: --limit must be >= 0")
    if args.delay_ms < 0:
        raise SystemExit("ERROR: --delay-ms must be >= 0")
    if hostname(args.index_url) not in ALLOWED_HOSTS:
        raise SystemExit("ERROR: index host must be İlkokul Akademi")

    records = scan(
        index_url=args.index_url,
        limit=args.limit,
        delay_ms=args.delay_ms,
    )
    print_report(records)


if __name__ == "__main__":
    main()
