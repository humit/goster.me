#!/usr/bin/env python3

from __future__ import annotations

import io
import os
import re
import threading
import time
from collections import OrderedDict, deque
from ipaddress import ip_address
from urllib.parse import parse_qs, urlparse

import adapters
import product_app
import public_app as legacy
from security import (
    SecurityValidationError,
    call_with_redirect_allowlist,
    public_origin,
    safe_urlopen,
    validate_public_url,
    validated_youtube_video_id,
)


HOST = product_app.HOST
PORT = product_app.PORT
STORE = product_app.STORE
PUBLIC_ORIGIN = public_origin()
MAX_POST_BYTES = int(os.environ.get("GOSTER_MAX_POST_BYTES", "4096"))
RESOLVE_RATE_PER_MINUTE = int(
    os.environ.get("GOSTER_RESOLVE_RATE_PER_MINUTE", "12")
)
TRUST_PROXY = os.environ.get("GOSTER_TRUST_PROXY", "0") == "1"
MAX_RATE_CLIENTS = int(os.environ.get("GOSTER_MAX_RATE_CLIENTS", "10000"))

_rate_lock = threading.Lock()
_rate_clients: OrderedDict[str, deque[float]] = OrderedDict()


_ORIGINAL_NORMALIZED_URL = adapters.normalized_url
_ORIGINAL_FETCH_HTML = adapters.fetch_html
_ORIGINAL_YOUTUBE_VIDEO_ID = adapters.YouTubeAdapter.video_id
_ORIGINAL_RESOLVE_URL = legacy.resolve_url


def hardened_normalized_url(url: str) -> str:
    try:
        return validate_public_url(url)
    except SecurityValidationError as exc:
        raise adapters.UnsupportedURL(str(exc)) from exc


def hardened_fetch_html(url: str, allowed_hosts: set[str]):
    return call_with_redirect_allowlist(
        _ORIGINAL_FETCH_HTML,
        url,
        allowed_hosts,
    )


def hardened_youtube_video_id(self, url: str) -> str | None:
    return validated_youtube_video_id(
        _ORIGINAL_YOUTUBE_VIDEO_ID(self, url)
    )


def hardened_resolve_url(url: str):
    item = _ORIGINAL_RESOLVE_URL(url)

    # Source HTML/JavaScript must never execute under the main goster.me
    # origin. Keep native/isolate content fail-closed until it is moved to
    # a separate sandbox origin.
    if item.render_mode == "isolate":
        raise adapters.UnsupportedURL(
            "This content type is temporarily unavailable for security reasons."
        )

    return item


def absolute_short_url(_handler, code: str) -> str:
    return f"{PUBLIC_ORIGIN}/{code}"


def install_runtime_hardening() -> None:
    # Adapter methods resolve these module globals at call time.
    adapters.normalized_url = hardened_normalized_url
    adapters.urlopen = safe_urlopen
    adapters.fetch_html = hardened_fetch_html
    adapters.YouTubeAdapter.video_id = hardened_youtube_video_id

    # public_app imported these symbols directly, so update its references too.
    legacy.resolve_url = hardened_resolve_url
    legacy.fetch_html = hardened_fetch_html

    # product_app uses this function for share pages and QR payloads.
    product_app.absolute_short_url = absolute_short_url


def _client_ip(handler) -> str:
    direct = handler.client_address[0]

    if not TRUST_PROXY:
        return direct

    try:
        direct_ip = ip_address(direct)
    except ValueError:
        return direct

    if not direct_ip.is_loopback:
        return direct

    forwarded = handler.headers.get("X-Forwarded-For", "")
    candidate = forwarded.split(",", 1)[0].strip()

    try:
        return str(ip_address(candidate))
    except ValueError:
        return direct


def _allow_resolve(client: str) -> bool:
    if RESOLVE_RATE_PER_MINUTE <= 0:
        return True

    now = time.monotonic()
    cutoff = now - 60.0

    with _rate_lock:
        bucket = _rate_clients.get(client)

        if bucket is None:
            if len(_rate_clients) >= MAX_RATE_CLIENTS:
                _rate_clients.popitem(last=False)

            bucket = deque()
            _rate_clients[client] = bucket
        else:
            _rate_clients.move_to_end(client)

        while bucket and bucket[0] <= cutoff:
            bucket.popleft()

        if len(bucket) >= RESOLVE_RATE_PER_MINUTE:
            return False

        bucket.append(now)
        return True


def _error_page(title: str, message: str) -> str:
    return product_app.product_document(
        title,
        f"""
<main class="share-page">
    <a class="product-wordmark" href="/">goster.me</a>
    <div class="share-card">
        <h1>{product_app.escape(title)}</h1>
        <p class="hero-copy">{product_app.escape(message)}</p>
        <a class="button" href="/">Geri dön</a>
    </div>
</main>
""",
    )


class Handler(product_app.Handler):
    server_version = "GosterMe/0.4-hardened"

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )
        super().end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        parts = [part for part in parsed.path.split("/") if part]

        # Never serve proxied source HTML/JS from the primary origin.
        if len(parts) == 2 and parts[0] == "v":
            self.send_error(404)
            return

        # Existing short links created before this hardening may reference
        # isolate mode. Fail them closed instead of rendering an iframe that
        # points at /v/<code>.
        if len(parts) == 1:
            code = parts[0].lower()

            if product_app.SHORT_CODE_RE.fullmatch(code):
                item = STORE.get(code, touch=False)

                if item is not None and item.render_mode == "isolate":
                    self.send_html(
                        410,
                        _error_page(
                            "İçerik geçici olarak kapalı",
                            "Bu içerik türü güvenlik izolasyonu tamamlanana kadar yayınlanmıyor.",
                        ),
                    )
                    return

        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path != "/resolve" or parsed.query:
            self.send_error(404)
            return

        if not _allow_resolve(_client_ip(self)):
            self.send_response(429)
            self.send_header("Retry-After", "60")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        content_type = self.headers.get("Content-Type", "")
        media_type = content_type.split(";", 1)[0].strip().lower()

        if media_type != "application/x-www-form-urlencoded":
            self.send_html(
                415,
                _error_page(
                    "Geçersiz istek",
                    "Bu form yalnızca standart URL form verisini kabul eder.",
                ),
            )
            return

        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0

        if length <= 0 or length > MAX_POST_BYTES:
            self.send_html(
                400,
                _error_page("Geçersiz istek", "İstek boyutu geçersiz."),
            )
            return

        try:
            raw = self.rfile.read(length)
            text = raw.decode("utf-8", errors="strict")
            data = parse_qs(
                text,
                keep_blank_values=True,
                strict_parsing=True,
                max_num_fields=4,
            )

            if set(data) != {"url"} or len(data["url"]) != 1:
                raise ValueError("Unexpected form fields.")

            url = validate_public_url(data["url"][0].strip())
            item = hardened_resolve_url(url)
            item_id = product_app.save_item(item)

        except (ValueError, SecurityValidationError, adapters.AdapterError):
            self.send_html(
                400,
                _error_page(
                    "Bağlantı desteklenmiyor",
                    "Bu bağlantı güvenli biçimde işlenemedi veya henüz desteklenmiyor.",
                ),
            )
            return

        except Exception as exc:
            request_id = f"{int(time.time()):x}-{threading.get_ident():x}"
            self.log_error(
                "resolve failed request_id=%s error=%r",
                request_id,
                exc,
            )
            self.send_html(
                500,
                _error_page(
                    "Bir sorun oluştu",
                    f"İstek işlenemedi. Hata kodu: {request_id}",
                ),
            )
            return

        self.redirect(f"/{item_id}")


install_runtime_hardening()


if __name__ == "__main__":
    purged = STORE.purge_expired()

    print(
        f"goster.me hardened listening on http://{HOST}:{PORT} "
        f"(public_origin={PUBLIC_ORIGIN}, purged={purged})",
        flush=True,
    )

    product_app.ThreadingHTTPServer(
        (HOST, PORT),
        Handler,
    ).serve_forever()
