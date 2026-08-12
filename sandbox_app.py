#!/usr/bin/env python3

from __future__ import annotations

import json
import os
import re
import sqlite3
import time

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import adapters
import public_app as legacy

from adapters import ResolvedContent
from sandbox_auth import signing_key, verify
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


def structural_isolation_script(selector: str) -> str:
    """Hide every sibling branch outside the selected activity root.

    The legacy renderer primarily uses CSS visibility. That is intentionally
    non-destructive, but source pages can override visibility with more
    specific `!important` rules and raw text nodes are not elements at all.
    This end-of-body pass keeps the selected root and its ancestor chain while
    removing sibling layout branches from the rendered view. Scripts/styles
    remain in the document and continue to execute normally.
    """
    selector_json = json.dumps(selector)

    return f"""
<script id="goster-structural-isolation">
(() => {{
    const root = document.querySelector({selector_json});

    if (!root || !document.body) {{
        return;
    }}

    const path = new Set([document.body]);
    let node = root;

    while (node && node !== document.body) {{
        path.add(node);
        node = node.parentElement;
    }}

    for (const parent of path) {{
        if (parent === root) {{
            continue;
        }}

        for (const child of Array.from(parent.children)) {{
            if (!path.has(child)) {{
                child.style.setProperty("display", "none", "important");
            }}
        }}

        for (const child of Array.from(parent.childNodes)) {{
            if (
                child.nodeType === Node.TEXT_NODE
                && child.textContent
                && child.textContent.trim()
            ) {{
                child.textContent = "";
            }}
        }}
    }}
}})();
</script>
"""


def inject_structural_isolation(value: str, selector: str) -> str:
    injection = structural_isolation_script(selector)
    lower = value.lower()
    body_pos = lower.rfind("</body>")

    if body_pos >= 0:
        return value[:body_pos] + injection + value[body_pos:]

    return value + injection


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


def valid_capability_query(code: str, query: str) -> bool:
    values = parse_qs(query, keep_blank_values=True)

    if set(values) != {"exp", "sig"}:
        return False

    if len(values["exp"]) != 1 or len(values["sig"]) != 1:
        return False

    try:
        return verify(code, values["exp"][0], values["sig"][0])
    except RuntimeError:
        return False


class Handler(BaseHTTPRequestHandler):
    server_version = "goster-sandbox"
    sys_version = ""

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("Cross-Origin-Resource-Policy", "same-site")
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
                    "sandbox allow-scripts allow-same-origin allow-modals allow-pointer-lock allow-presentation",
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

        if parsed.fragment:
            self.send_error(404)
            return

        parts = [part for part in parsed.path.split("/") if part]

        if len(parts) != 2 or parts[0] != "v":
            self.send_error(404)
            return

        code = parts[1].lower()

        if not valid_code(code) or not valid_capability_query(code, parsed.query):
            self.send_error(404)
            return

        # Real browsers disclose top-level navigation as "document" and an
        # iframe navigation as "iframe". Reject browser top-level access when
        # this signal is present. The signed capability URL remains the actual
        # authorization control because HTTP clients can forge this header.
        fetch_dest = self.headers.get("Sec-Fetch-Dest", "").strip().lower()
        if fetch_dest and fetch_dest != "iframe":
            self.send_error(404)
            return

        item = load_item_readonly(code)

        if item is None:
            self.send_error(404)
            return

        try:
            page = legacy.render_isolated_source(item)
            page = strip_known_tracking_html(page)
            page = inject_structural_isolation(page, item.selector or "body")
        except Exception as exc:
            self.log_error("sandbox render failed code=%s error=%r", code, exc)
            self.send_error(502)
            return

        self.send_html(200, page)

    def do_POST(self) -> None:
        self.send_error(405)


if __name__ == "__main__":
    # Fail closed before accepting traffic if deployment forgot the shared
    # sandbox capability secret.
    signing_key()

    print(
        f"goster sandbox listening on http://{HOST}:{PORT} "
        f"(database={DATABASE_PATH}, parent={MAIN_ORIGIN})",
        flush=True,
    )

    ThreadingHTTPServer((HOST, PORT), Handler).serve_forever()
