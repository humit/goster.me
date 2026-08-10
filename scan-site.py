#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import json
import time
from collections import Counter, defaultdict, deque
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

from adapters import (
    NativeGameFingerprintParser,
    fetch_html,
    hostname,
    matching_adapters,
    resolve_url,
)


ASSET_SUFFIXES = {
    ".css", ".js", ".json", ".xml", ".txt",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
    ".mp3", ".wav", ".ogg", ".mp4", ".webm", ".pdf", ".zip",
    ".woff", ".woff2", ".ttf", ".eot",
}

GAME_HINTS = (
    "oyun",
    "game",
    "quiz",
    "test",
    "hizliokuma",
    "okuma",
    "ritmik",
    "alfabe",
    "ses-",
    "1912",
)


class DiscoveryParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.links: list[str] = []
        self.scripts: list[str] = []
        self.stylesheets: list[str] = []
        self.ids: set[str] = set()
        self.classes: set[str] = set()
        self.title_parts: list[str] = []
        self.in_title = False

    def handle_starttag(self, tag: str, attrs) -> None:
        tag = tag.lower()
        attrs = dict(attrs)

        element_id = attrs.get("id")
        if element_id:
            self.ids.add(element_id)

        self.classes.update(attrs.get("class", "").split())

        if tag == "title":
            self.in_title = True
        elif tag == "a" and attrs.get("href"):
            self.links.append(attrs["href"])
        elif tag == "script" and attrs.get("src"):
            self.scripts.append(attrs["src"])
        elif tag == "link" and attrs.get("href"):
            rel = attrs.get("rel", "")
            if "stylesheet" in rel.lower():
                self.stylesheets.append(attrs["href"])

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data: str) -> None:
        if self.in_title:
            value = data.strip()
            if value:
                self.title_parts.append(value)

    @property
    def title(self) -> str | None:
        value = " ".join(self.title_parts).strip()
        return value or None


def canonical_url(url: str) -> str:
    clean, _ = urldefrag(url)
    parsed = urlparse(clean)
    path = parsed.path or "/"
    return urlunparse((
        parsed.scheme.lower(),
        parsed.netloc.lower(),
        path,
        "",
        "",
        "",
    ))


def is_html_candidate(url: str, allowed_hosts: set[str]) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if (parsed.hostname or "").lower() not in allowed_hosts:
        return False

    suffix = Path(parsed.path).suffix.lower()
    return suffix not in ASSET_SUFFIXES


def looks_game_like(url: str, parser: DiscoveryParser) -> bool:
    value = (url + " " + (parser.title or "")).lower()

    if any(hint in value for hint in GAME_HINTS):
        return True

    game_tokens = {
        "game", "oyun", "quiz", "question", "questionblock",
        "soru", "cevap", "cevaplar", "score", "puan",
        "basla", "start", "result", "sonuc",
    }

    return bool(
        game_tokens.intersection(parser.ids)
        or game_tokens.intersection(parser.classes)
    )


def resource_signature(base_url: str, parser: DiscoveryParser) -> tuple[str, list[str]]:
    resources: list[str] = []

    for raw in parser.scripts + parser.stylesheets:
        absolute = urljoin(base_url, raw)
        parsed = urlparse(absolute)
        if not parsed.hostname:
            continue
        resources.append(f"{parsed.hostname}{parsed.path}")

    structural = [
        *(f"#{value}" for value in sorted(parser.ids)),
        *(f".{value}" for value in sorted(parser.classes)),
    ]

    payload = "\n".join(sorted(set(resources)) + structural).encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()[:12]
    return digest, sorted(set(resources))


def build_robots(start_url: str) -> RobotFileParser:
    parsed = urlparse(start_url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    parser = RobotFileParser()
    parser.set_url(robots_url)
    try:
        parser.read()
    except Exception:
        # Fail open for robots fetch errors, but remain bounded and rate-limited.
        pass
    return parser


def scan(start_url: str, max_pages: int, delay: float) -> dict:
    start_url = canonical_url(start_url)
    host = hostname(start_url)
    allowed_hosts = {host}
    if host.startswith("www."):
        allowed_hosts.add(host.removeprefix("www."))
    else:
        allowed_hosts.add("www." + host)

    robots = build_robots(start_url)
    queue = deque([start_url])
    queued = {start_url}
    visited: set[str] = set()
    rows: list[dict] = []

    while queue and len(visited) < max_pages:
        url = queue.popleft()
        if url in visited:
            continue
        visited.add(url)

        if not robots.can_fetch("*", url):
            rows.append({"url": url, "status": "robots-denied"})
            continue

        try:
            final_url, document = fetch_html(
                url,
                allowed_hosts=allowed_hosts,
            )
        except Exception as exc:
            rows.append({
                "url": url,
                "status": "fetch-error",
                "error": str(exc),
            })
            time.sleep(delay)
            continue

        parser = DiscoveryParser()
        parser.feed(document)

        for raw_link in parser.links:
            candidate = canonical_url(urljoin(final_url, raw_link))
            if candidate in queued or candidate in visited:
                continue
            if not is_html_candidate(candidate, allowed_hosts):
                continue
            queued.add(candidate)
            queue.append(candidate)

        if not looks_game_like(final_url, parser):
            rows.append({
                "url": final_url,
                "title": parser.title,
                "status": "non-game",
            })
            time.sleep(delay)
            continue

        signature, resources = resource_signature(final_url, parser)
        adapters = matching_adapters(final_url)

        row = {
            "url": final_url,
            "title": parser.title,
            "status": "candidate",
            "matching_adapters": adapters,
            "family_signature": signature,
            "resources": resources,
            "ids": sorted(parser.ids),
            "classes": sorted(parser.classes),
        }

        try:
            resolved = resolve_url(final_url)
            row.update({
                "status": "resolved",
                "adapter": resolved.adapter,
                "provider": resolved.provider,
                "kind": resolved.kind,
                "render_mode": resolved.render_mode,
                "selector": resolved.selector,
            })
        except Exception as exc:
            row.update({
                "status": "known-host-unresolved" if adapters else "unsupported",
                "error": str(exc),
            })

        rows.append(row)
        time.sleep(delay)

    family_members: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        signature = row.get("family_signature")
        if signature:
            family_members[signature].append(row)

    families = []
    for signature, members in family_members.items():
        statuses = Counter(member["status"] for member in members)
        adapters = Counter(
            member.get("adapter") or "unresolved"
            for member in members
        )
        families.append({
            "signature": signature,
            "count": len(members),
            "statuses": dict(statuses),
            "adapters": dict(adapters),
            "representative_url": members[0]["url"],
            "representative_title": members[0].get("title"),
        })

    families.sort(key=lambda item: (-item["count"], item["signature"]))

    return {
        "start_url": start_url,
        "visited_pages": len(visited),
        "queued_pages": len(queued),
        "counts": dict(Counter(row["status"] for row in rows)),
        "families": families,
        "pages": rows,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Crawl a source site and measure adapter compatibility by game family."
    )
    parser.add_argument("start_url")
    parser.add_argument("--max-pages", type=int, default=200)
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--output", default="site-scan.json")
    args = parser.parse_args()

    report = scan(args.start_url, args.max_pages, args.delay)

    output = Path(args.output)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Visited : {report['visited_pages']}")
    print(f"Queued  : {report['queued_pages']}")
    for status, count in sorted(report["counts"].items()):
        print(f"{status:22} {count}")

    print("\nFamilies:")
    for family in report["families"][:30]:
        status_text = ", ".join(
            f"{key}={value}"
            for key, value in sorted(family["statuses"].items())
        )
        print(
            f"{family['signature']}  {family['count']:4}  "
            f"{status_text}  {family['representative_url']}"
        )

    print(f"\nReport: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
