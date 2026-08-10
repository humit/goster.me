#!/usr/bin/env python3

from __future__ import annotations

import argparse
import hashlib
import heapq
import json
import time
from collections import Counter, defaultdict
from html.parser import HTMLParser
from itertools import count
from pathlib import Path
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse
from urllib.robotparser import RobotFileParser

from adapters import fetch_html, hostname, matching_adapters, resolve_url


ASSET_SUFFIXES = {
    ".css", ".js", ".json", ".xml", ".txt",
    ".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg", ".ico",
    ".mp3", ".wav", ".ogg", ".mp4", ".webm", ".pdf", ".zip",
    ".woff", ".woff2", ".ttf", ".eot",
}

STRONG_GAME_HINTS = (
    "oyun", "game", "quiz", "hizli-okuma", "hizliokuma",
    "carpim", "ritmik", "alfabe", "ezberleme", "mini-zeka",
)

WEAK_GAME_HINTS = (
    "test", "soru", "etkinlik", "okuma",
)

LOW_VALUE_PATH_HINTS = (
    "/login", "/odev/", "/tools-1912/", "/sinifim/",
    "/test-coz/", "/ogrenci-takip",
)

TRACKER_RESOURCE_HINTS = (
    "googletagmanager.com", "googlesyndication.com", "doubleclick.net",
    "google-analytics.com", "cloudflareinsights.com",
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
        parsed.scheme.lower(), parsed.netloc.lower(), path, "", "", "",
    ))


def is_html_candidate(url: str, allowed_hosts: set[str]) -> bool:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"}:
        return False
    if (parsed.hostname or "").lower() not in allowed_hosts:
        return False
    return Path(parsed.path).suffix.lower() not in ASSET_SUFFIXES


def crawl_priority(url: str) -> int:
    value = url.lower()
    score = 0
    score += 12 * sum(hint in value for hint in STRONG_GAME_HINTS)
    score += 2 * sum(hint in value for hint in WEAK_GAME_HINTS)
    score -= 15 * sum(hint in value for hint in LOW_VALUE_PATH_HINTS)
    return score


def game_score(url: str, parser: DiscoveryParser) -> tuple[int, list[str]]:
    value = (url + " " + (parser.title or "")).lower()
    ids = parser.ids
    classes = parser.classes
    reasons: list[str] = []
    score = 0

    strong = [hint for hint in STRONG_GAME_HINTS if hint in value]
    weak = [hint for hint in WEAK_GAME_HINTS if hint in value]
    low_value = [hint for hint in LOW_VALUE_PATH_HINTS if hint in url.lower()]

    if strong:
        score += 4
        reasons.append("strong-url-title:" + ",".join(strong[:4]))
    if weak:
        score += 1
        reasons.append("weak-url-title:" + ",".join(weak[:4]))
    if low_value:
        score -= 5
        reasons.append("low-value-path:" + ",".join(low_value[:3]))

    tokens = ids | classes

    if {"questionblock", "cevaplar"}.issubset(tokens):
        score += 5
        reasons.append("dom:questionblock+cevaplar")
    if ({"soru", "cevap"}.issubset(tokens) or {"soru", "cevaplar"}.issubset(tokens)):
        score += 4
        reasons.append("dom:soru+cevap")
    if ({"score", "start"}.issubset(tokens) or {"puan", "basla"}.issubset(tokens)):
        score += 4
        reasons.append("dom:score+start")
    if ({"game", "score"}.issubset(tokens) or {"oyun", "puan"}.issubset(tokens)):
        score += 3
        reasons.append("dom:game+score")
    if any(token in tokens for token in {"question", "question-text", "options-container"}):
        score += 2
        reasons.append("dom:question-ui")

    return score, reasons


def resource_signature(base_url: str, parser: DiscoveryParser) -> tuple[str, list[str]]:
    resources: list[str] = []

    for raw in parser.scripts + parser.stylesheets:
        absolute = urljoin(base_url, raw)
        parsed = urlparse(absolute)
        if not parsed.hostname:
            continue
        resource = f"{parsed.hostname}{parsed.path}"
        if any(hint in resource for hint in TRACKER_RESOURCE_HINTS):
            continue
        resources.append(resource)

    stable_tokens = {
        "game", "oyun", "quiz", "question", "questionblock", "soru",
        "cevap", "cevaplar", "score", "puan", "start", "basla",
        "result", "sonuc", "container", "game-container", "game-wrapper",
        "options-container", "question-text", "sahne1", "sahne2",
    }
    structural = [
        *(f"#{value}" for value in sorted(parser.ids) if value in stable_tokens),
        *(f".{value}" for value in sorted(parser.classes) if value in stable_tokens),
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
        pass
    return parser


def scan(
    start_url: str,
    max_pages: int,
    delay: float,
    min_game_score: int,
    max_candidates: int | None,
) -> dict:
    start_url = canonical_url(start_url)
    host = hostname(start_url)
    allowed_hosts = {host}
    allowed_hosts.add(host.removeprefix("www.") if host.startswith("www.") else "www." + host)

    robots = build_robots(start_url)
    sequence = count()
    queue: list[tuple[int, int, str]] = []
    heapq.heappush(queue, (-1000, next(sequence), start_url))
    queued = {start_url}
    visited: set[str] = set()
    rows: list[dict] = []
    candidate_count = 0

    while queue and len(visited) < max_pages:
        if max_candidates is not None and candidate_count >= max_candidates:
            break

        _, _, url = heapq.heappop(queue)
        if url in visited:
            continue
        visited.add(url)

        if not robots.can_fetch("*", url):
            rows.append({"url": url, "status": "robots-denied"})
            continue

        try:
            final_url, document = fetch_html(url, allowed_hosts=allowed_hosts)
        except Exception as exc:
            rows.append({"url": url, "status": "fetch-error", "error": str(exc)})
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
            heapq.heappush(
                queue,
                (-crawl_priority(candidate), next(sequence), candidate),
            )

        score, reasons = game_score(final_url, parser)
        if score < min_game_score:
            rows.append({
                "url": final_url,
                "title": parser.title,
                "status": "non-game",
                "game_score": score,
                "game_reasons": reasons,
            })
            time.sleep(delay)
            continue

        candidate_count += 1
        signature, resources = resource_signature(final_url, parser)
        adapters = matching_adapters(final_url)
        row = {
            "url": final_url,
            "title": parser.title,
            "status": "candidate",
            "game_score": score,
            "game_reasons": reasons,
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
        adapters = Counter(member.get("adapter") or "unresolved" for member in members)
        families.append({
            "signature": signature,
            "count": len(members),
            "statuses": dict(statuses),
            "adapters": dict(adapters),
            "representative_url": members[0]["url"],
            "representative_title": members[0].get("title"),
            "max_game_score": max(member.get("game_score", 0) for member in members),
        })

    families.sort(key=lambda item: (-item["count"], -item["max_game_score"], item["signature"]))

    return {
        "start_url": start_url,
        "visited_pages": len(visited),
        "queued_pages": len(queued),
        "candidate_pages": candidate_count,
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
    parser.add_argument("--max-candidates", type=int)
    parser.add_argument("--min-game-score", type=int, default=4)
    parser.add_argument("--delay", type=float, default=0.25)
    parser.add_argument("--output", default="site-scan.json")
    args = parser.parse_args()

    report = scan(
        args.start_url,
        args.max_pages,
        args.delay,
        args.min_game_score,
        args.max_candidates,
    )

    output = Path(args.output)
    output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"Visited    : {report['visited_pages']}")
    print(f"Queued     : {report['queued_pages']}")
    print(f"Candidates : {report['candidate_pages']}")
    for status, count_value in sorted(report["counts"].items()):
        print(f"{status:22} {count_value}")

    print("\nFamilies:")
    for family in report["families"][:30]:
        status_text = ", ".join(
            f"{key}={value}" for key, value in sorted(family["statuses"].items())
        )
        print(
            f"{family['signature']}  {family['count']:4}  "
            f"score={family['max_game_score']:2}  "
            f"{status_text}  {family['representative_url']}"
        )

    print(f"\nReport: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
