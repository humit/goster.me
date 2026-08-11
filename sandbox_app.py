#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import sqlite3
import time

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import adapters
import public_app as legacy

from adapters import ResolvedContent
from security import call_with_redirect_allowlist, safe_urlopen
from shortlinks import SHORT_CODE_ALPHABET, SHORT_CODE_LENGTH


HOST = os.environ.get("GOSTER_SANDBOX_HOST", "127.0.0.1")
PORT = int(os.environ.get("GOSTER_SANDBOX_PORT", "8092"))
DATABASE_PATH = Path(
    os.environ.get(
        "GOSTER_DATABASE",
        "/var/lib/goster.me/goster.sqlite3",
    )
)
MAIN_ORIGIN = os.environ.get("GOSTER_PUBLIC_ORIGIN", "https://goster.me").rstrip("/")

_ORIGINAL_FETCH_HTML = adapters.fetch_html

_TRACKING_HOSTS = (
    "googletagmanager.com",
    "googlesyndication.com",
    "google-analytics.com",
    "doubleclick.net",
)
_SCRIPT_BLOCK_RE = re.compile(
    r"<script\b(?P<attrs>[^>]*)>(?P<body>.*?)</script\s*>",
    re.IGNORECASE | re.DOTALL,
)
_IFRAME_BLOCK_RE = re.compile(
    r"<iframe\b(?P<attrs>[^>]*)>(?P<body>.*?)</iframe\s*>",
    re.IGNORECASE | re.DOTALL,
)


def hardened_fetch_html(url: str, allowed_hosts: set[str]):
    return call_with_redirect_allowlist(
        _ORIGINAL_FETCH_HTML,
        url,
        allowed_hosts,
    )


# render_isolated_source() imported fetch_html directly in public_app, so both
# module references are replaced. urllib redirects are validated before open.
adapters.urlopen = safe_urlopen
adapters.fetch_html = hardened_fetch_html
legacy.fetch_html = hardened_fetch_html


def strip_known_tracking_html(value: str) -> str:
    """Remove common analytics/ad execution blocks before browser parsing.

    Isolation protects the primary origin, but known analytics and advertising
    scripts are unnecessary for the child-facing activity and should not be
    fetched or executed by the sandboxed document.
    """

    def strip_script(match: re.Match[str]) -> str:
        attrs = match.group("attrs").lower()
        body = match.group("body").lower()

        if any(host in attrs for host in _TRACKING_HOSTS):
            return ""

        # Common inline Google Analytics bootstrap paired with gtag.js.
        if "gtag(" in body and "datalayer" in body:
            return ""

        return match.group(0)

    def strip_iframe(match: re.Match[str]) -> str:
        attrs = match.group("attrs").lower()
        if any(host in attrs for host in _TRACKING_HOSTS):
            return ""
        return match.group(0)

    value = _SCRIPT_BLOCK_RE.sub(strip_script, value)
    value = _IFRAME_BLOCK_RE.sub(strip_iframe, value)
    return value


def valid_code(code: str) -> bool:
    normalized = code.strip().lower()
    return (
        len(normalized) == SHORT_CODE_LENGTH
        and all(ch in SHORT_CODE_ALPHABET for ch in normalized)
    )


def load_item_readonly(
    code: str,
    *,
    now: int | None = None,
) -> ResolvedContent | None:
    normalized = code.strip().lower()

    if not valid_code(normalized):
        return None

    timestamp = int(time.time() if now is None else now)
    database_uri = f"file:{DATABASE_PATH}?mode=ro"

    try:
        db = sqlite3.connect(
            database_uri,
            uri=True,
            timeout=5,
        )
    except sqlite3.Error:
        return None

    db.row_factory = sqlite3.Row

    try:
        row = db.execute(
            """
            SELECT payload_json, expires_at
            FROM short_links
            WHERE code = ?
            """,
            (normalized,),
        ).fetchone()
    except sqlite3.Error:
        return None
    finally:
        db.close()

    if row is None or int(row["expires_at"]) <= timestamp:
        return None

    try:
        data = json.loads(row["payload_json"])
        data["content_urls"] = tuple(data.get("content_urls") or ())
        item = ResolvedContent(**data)
    except (TypeError, ValueError, KeyError, json.JSONDecodeError):
        return None

    if item.render_mode != "isolate":
        return None

    return item


class Handler(BaseHTTPRequestHandler):
    server_version = "goster-sandbox"
    sys_version = ""

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        # Do not emit X-Frame-Options here: this response must be framed by
        # goster.me. frame-ancestors below is the authoritative allowlist.
        self.send_header(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=(), usb=(), serial=()",
        )
        self.send_header(
            "Content-Security-Policy",
            "; ".join(
                (
                    "default-src https: data: blob:",
                    "script-src https: 'unsafe-inline' 'unsafe-eval'",
                    "style-src https: 'unsafe-inline'",
                    "img-src https: data: blob:",
                    "font-src https: data:",
                    "media-src https: data: blob:",
                    "connect-src https:",
                    "frame-src https:",
                    "object-src 'none'",
                    "form-action 'none'",
                    "base-uri https:",
                    f"frame-ancestors {MAIN_ORIGIN}",
                    "sandbox allow-scripts allow-modals allow-pointer-lock allow-presentation",
                )
            ),
        )
        super().end_headers()

    def send_html(self, status: int, value: str) -> None:
        body = value.encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        parsed = urlparse(self.path)

        if parsed.query or parsed.fragment:
            self.send_error(404)
            return

        parts = [part for part in parsed.path.split("/") if part]

        if len(parts) != 2 or parts[0] != "v":
            self.send_error(404)
            return

        code = parts[1].lower()
        item = load_item_readonly(code)

        if item is None:
            self.send_error(404)
            return

        try:
            page = legacy.render_isolated_source(item)
            page = strip_known_tracking_html(page)
        except Exception as exc:
            self.log_error("sandbox render failed code=%s error=%r", code, exc)
            self.send_error(502)
            return

        self.send_html(200, page)

    def do_POST(self) -> None:
        self.send_error(405)


if __name__ == "__main__":
    print(
        f"goster sandbox listening on http://{HOST}:{PORT} "
        f"(database={DATABASE_PATH}, parent={MAIN_ORIGIN})",
        flush=True,
    )

    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
