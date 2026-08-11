#!/usr/bin/env python3

from __future__ import annotations

import html
import io
import os
import random
import re
import threading
import time

from collections import OrderedDict, deque
from http.server import ThreadingHTTPServer
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import segno

import adapters
import public_app as legacy

from security import (
    SecurityValidationError,
    call_with_redirect_allowlist,
    public_origin,
    safe_urlopen,
    validate_public_url,
    validated_youtube_video_id,
)
from shortlinks import (
    DEFAULT_TTL_SECONDS,
    SHORT_CODE_ALPHABET,
    SHORT_CODE_LENGTH,
    ShortLinkStore,
)


HOST = os.environ.get("GOSTER_HOST", legacy.HOST)
PORT = int(os.environ.get("GOSTER_PORT", str(legacy.PORT)))
STORE = ShortLinkStore()
ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
PUBLIC_ORIGIN = public_origin()
MAX_POST_BYTES = int(os.environ.get("GOSTER_MAX_POST_BYTES", "4096"))
RESOLVE_RATE_PER_MINUTE = int(
    os.environ.get("GOSTER_RESOLVE_RATE_PER_MINUTE", "12")
)
TRUST_PROXY = os.environ.get("GOSTER_TRUST_PROXY", "0") == "1"
MAX_RATE_CLIENTS = int(os.environ.get("GOSTER_MAX_RATE_CLIENTS", "10000"))

SLOGANS = (
    "Bana reklam goster.me.",
    "Çocuğuma dikkat dağıtıcı şeyler goster.me.",
    "Karmakarışık bir sayfa goster.me.",
    "Videoyu göster. YouTube'u goster.me.",
    "İçeriği göster. Gerisini goster.me.",
)

SHORT_CODE_RE = re.compile(
    rf"^[{re.escape(SHORT_CODE_ALPHABET)}]"
    rf"{{{SHORT_CODE_LENGTH}}}$"
)

_rate_lock = threading.Lock()
_rate_clients: OrderedDict[str, deque[float]] = OrderedDict()

_ORIGINAL_FETCH_HTML = adapters.fetch_html
_ORIGINAL_YOUTUBE_VIDEO_ID = adapters.YouTubeAdapter.video_id
_ORIGINAL_RESOLVE_URL = legacy.resolve_url


def escape(value: str | None) -> str:
    return html.escape(value or "", quote=True)


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

    # Never execute fetched third-party HTML/JavaScript under the primary
    # goster.me origin. Native/isolate content stays fail-closed until it is
    # moved to a dedicated sandbox origin.
    if item.render_mode == "isolate":
        raise adapters.UnsupportedURL(
            "This content type is temporarily unavailable for security reasons."
        )

    return item


def install_runtime_hardening() -> None:
    # Adapter functions resolve these globals at call time.
    adapters.normalized_url = hardened_normalized_url
    adapters.urlopen = safe_urlopen
    adapters.fetch_html = hardened_fetch_html
    adapters.YouTubeAdapter.video_id = hardened_youtube_video_id

    # public_app imported these symbols directly, so update its references.
    legacy.resolve_url = hardened_resolve_url
    legacy.fetch_html = hardened_fetch_html


install_runtime_hardening()


def save_item(item):
    return STORE.save(item)


def get_item(item_id: str):
    return STORE.get(item_id)


# Existing renderer functions resolve these names from public_app's module
# globals. Replacing them lets the mature renderer gain persistence without
# forking all adapter/rendering logic.
legacy.save_item = save_item
legacy.get_item = get_item


LEGACY_DOCUMENT = legacy.document


def product_document(title: str, body: str) -> str:
    """Shared HTML shell.

    Presentation lives in static/product.css and behavior in static/product.js
    so contributors can work on UI without editing the Python renderer.
    """
    return f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0d1117">
<title>{escape(title)}</title>
{legacy.BASE_STYLE}
<link rel="stylesheet" href="/static/product.css">
</head>
<body>
{body}
<script src="/static/product.js" defer></script>
</body>
</html>
"""


legacy.document = product_document


def render_home() -> str:
    slogan = random.choice(SLOGANS)

    return product_document(
        "goster.me — Gerekmeyeni gösterme",
        f"""
<main class="product-home">
    <header class="product-header">
        <a class="product-wordmark" href="/">goster.me</a>
    </header>

    <section class="hero" aria-labelledby="hero-title">
        <p class="eyebrow">İçerik, gürültü olmadan.</p>
        <h1 id="hero-title">
            Gerekmeyen hiçbir şeyi<br>
            <span class="domain-punch">goster.me</span>
        </h1>

        <p class="hero-copy">
            Bir bağlantı ver. İstediğin içeriği ayıklayalım ve
            kısa, kolay paylaşılabilir bir adreste gösterelim.
        </p>

        <form class="url-form product-url-form" method="post" action="/resolve">
            <label for="url">Bağlantı</label>
            <input
                id="url"
                name="url"
                type="url"
                inputmode="url"
                autocomplete="off"
                autocapitalize="off"
                spellcheck="false"
                placeholder="Bir bağlantı yapıştır…"
                maxlength="2048"
                required
                autofocus
            >
            <button class="url-submit" type="submit">Göster</button>
        </form>

        <p class="current-slogan">{escape(slogan)}</p>
    </section>

    <section class="manifesto" aria-labelledby="manifesto-title">
        <h2 id="manifesto-title">Neden?</h2>
        <p class="manifesto-lead">
            İçeriğe erişmek, onu çevreleyen dikkat ekonomisini kabul etmek değildir.
        </p>
        <p>
            Bir videoyu, oyunu, ödevi ya da etkinliği görmek için reklamları,
            önerileri, otomatik oynatmayı ve gereksiz sayfa kalabalığını da
            görmek zorunda değiliz. Özellikle çocuklarımız için.
        </p>
    </section>

    <footer class="product-footer">
        <span>Kısa adres. Temiz içerik.</span>
        <a href="https://github.com/humit/goster.me" rel="noopener noreferrer" target="_blank">
            Açık kaynak ↗
        </a>
    </footer>
</main>
""",
    )


def branded_preview_actions(
    item_id: str,
    *,
    back_href: str = "/",
) -> str:
    canonical = f"/{escape(item_id)}"

    return f"""
<div class="viewer-toolbar product-viewer-toolbar">
    <div class="viewer-toolbar-group product-viewer-left">
        <a class="viewer-icon" href="{escape(back_href)}" aria-label="Geri dön" title="Geri dön">←</a>
        <a class="viewer-brand" href="/">goster.me</a>
    </div>

    <div class="viewer-toolbar-group product-viewer-actions">
        <button
            class="viewer-action"
            type="button"
            data-action="copy"
            data-url="{canonical}"
            aria-label="Bağlantıyı kopyala"
        >Kopyala</button>
        <button
            class="viewer-action"
            type="button"
            data-action="share"
            data-url="{canonical}"
            aria-label="Paylaş"
        >Paylaş</button>
        <a
            class="viewer-action"
            href="/q/{escape(item_id)}"
            data-action="qr"
            aria-label="QR kodu göster"
        >QR</a>
    </div>
</div>
"""


legacy.render_home = render_home
legacy.preview_actions = branded_preview_actions


def absolute_short_url(_handler, code: str) -> str:
    # Never derive public URLs from untrusted Host/X-Forwarded-* headers.
    return f"{PUBLIC_ORIGIN}/{code}"


def render_expired(code: str) -> str:
    return product_document(
        "Bağlantının süresi doldu",
        f"""
<main class="share-page">
    <a class="product-wordmark" href="/">goster.me</a>
    <div class="share-card">
        <h1>Bu bağlantının süresi doldu.</h1>
        <p class="hero-copy">
            Kısa bağlantılar geçicidir. Kaynak bağlantı elindeyse yeniden
            goster.me ve yeni bir kısa adres oluştur.
        </p>
        <a class="button" href="/">Yeni bağlantı oluştur</a>
        <p class="source">Kod: {escape(code)}</p>
    </div>
</main>
""",
    )


def render_share_page(code: str, short_url: str) -> str:
    return product_document(
        "Paylaş — goster.me",
        f"""
<main class="share-page">
    <a class="product-wordmark" href="/">goster.me</a>

    <div class="share-card">
        <img
            class="qr-image"
            src="/qr/{escape(code)}.svg"
            alt="{escape(short_url)} için QR kodu"
        >

        <div class="short-url">{escape(short_url)}</div>

        <div class="share-actions">
            <a class="viewer-action" href="/{escape(code)}">Aç</a>
            <button
                class="viewer-action"
                type="button"
                data-action="copy"
                data-url="/{escape(code)}"
            >Kopyala</button>
            <button
                class="viewer-action"
                type="button"
                data-action="share"
                data-url="/{escape(code)}"
            >Paylaş</button>
        </div>
    </div>
</main>
""",
    )


def render_security_error(title: str, message: str) -> str:
    return product_document(
        title,
        f"""
<main class="share-page">
    <a class="product-wordmark" href="/">goster.me</a>
    <div class="share-card">
        <h1>{escape(title)}</h1>
        <p class="hero-copy">{escape(message)}</p>
        <a class="button" href="/">Geri dön</a>
    </div>
</main>
""",
    )


def client_ip(handler) -> str:
    direct = handler.client_address[0]

    if not TRUST_PROXY:
        return direct

    try:
        direct_ip = ip_address(direct)
    except ValueError:
        return direct

    # Only trust X-Forwarded-For from a local reverse proxy.
    if not direct_ip.is_loopback:
        return direct

    forwarded = handler.headers.get("X-Forwarded-For", "")
    candidate = forwarded.split(",", 1)[0].strip()

    try:
        return str(ip_address(candidate))
    except ValueError:
        return direct


def allow_resolve(client: str) -> bool:
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


class Handler(legacy.Handler):
    server_version = "GosterMe/0.4"

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        self.send_header(
            "Permissions-Policy",
            "camera=(), microphone=(), geolocation=(), payment=()",
        )
        super().end_headers()

    def send_bytes(
        self,
        status: int,
        value: bytes,
        content_type: str,
        *,
        cache_control: str = "no-store",
    ) -> None:
        self.send_response(status)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(value)))
        self.send_header("Cache-Control", cache_control)
        self.end_headers()
        self.wfile.write(value)

    def send_static(self, name: str) -> bool:
        allowed = {
            "product.css": "text/css; charset=utf-8",
            "product.js": "text/javascript; charset=utf-8",
        }

        content_type = allowed.get(name)
        if content_type is None:
            return False

        path = STATIC_DIR / name

        try:
            body = path.read_bytes()
        except OSError:
            self.send_error(404)
            return True

        self.send_bytes(
            200,
            body,
            content_type,
            cache_control="public, max-age=300",
        )
        return True

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        parts = [part for part in path.split("/") if part]

        # Source HTML/JavaScript must never be served from the main origin.
        if len(parts) == 2 and parts[0] == "v":
            self.send_error(404)
            return

        if len(parts) == 2 and parts[0] == "static":
            if self.send_static(parts[1]):
                return

        if len(parts) == 2 and parts[0] == "q":
            code = parts[1].lower()

            if SHORT_CODE_RE.fullmatch(code):
                item = STORE.get(code, touch=False)
                if item is None:
                    self.send_html(410, render_expired(code))
                    return

                self.send_html(
                    200,
                    render_share_page(
                        code,
                        absolute_short_url(self, code),
                    ),
                )
                return

        if len(parts) == 2 and parts[0] == "qr" and parts[1].endswith(".svg"):
            code = parts[1][:-4].lower()

            if SHORT_CODE_RE.fullmatch(code):
                item = STORE.get(code, touch=False)
                if item is None:
                    self.send_error(410)
                    return

                qr = segno.make(
                    absolute_short_url(self, code),
                    micro=False,
                    error="m",
                )
                buffer = io.BytesIO()
                qr.save(
                    buffer,
                    kind="svg",
                    scale=6,
                    border=4,
                    dark="#111111",
                    light="#ffffff",
                )
                self.send_bytes(
                    200,
                    buffer.getvalue(),
                    "image/svg+xml; charset=utf-8",
                    cache_control="private, max-age=300",
                )
                return

        # Canonical public form: goster.me/abc346
        if len(parts) == 1:
            code = parts[0].lower()

            if SHORT_CODE_RE.fullmatch(code):
                item = STORE.get(code, touch=False)

                if item is None:
                    self.send_html(410, render_expired(code))
                    return

                if item.render_mode == "isolate":
                    self.send_html(
                        410,
                        render_security_error(
                            "İçerik geçici olarak kapalı",
                            "Bu içerik türü güvenlik izolasyonu tamamlanana kadar yayınlanmıyor.",
                        ),
                    )
                    return

                # Count only content that is actually served.
                item = STORE.get(code)

                self.send_html(
                    200,
                    legacy.render_child(code, item),
                )
                return

        # Compatibility for links created by the earlier public prototype.
        if len(parts) == 2 and parts[0] == "g":
            code = parts[1].lower()
            item = STORE.get(code, touch=False)

            if item is not None:
                self.redirect(f"/{code}")
                return

        super().do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path != "/resolve" or parsed.query:
            self.send_error(404)
            return

        if not allow_resolve(client_ip(self)):
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
                render_security_error(
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
                render_security_error(
                    "Geçersiz istek",
                    "İstek boyutu geçersiz.",
                ),
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
            item_id = save_item(item)

        except (ValueError, SecurityValidationError, adapters.AdapterError):
            self.send_html(
                400,
                render_security_error(
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
                render_security_error(
                    "Bir sorun oluştu",
                    f"İstek işlenemedi. Hata kodu: {request_id}",
                ),
            )
            return

        self.redirect(f"/{item_id}")


def ttl_days() -> float:
    return DEFAULT_TTL_SECONDS / (24 * 60 * 60)


if __name__ == "__main__":
    purged = STORE.purge_expired()

    print(
        f"goster.me listening on http://{HOST}:{PORT} "
        f"(public_origin={PUBLIC_ORIGIN}, short={SHORT_CODE_LENGTH}, "
        f"ttl={ttl_days():g}d, purged={purged})",
        flush=True,
    )

    ThreadingHTTPServer(
        (HOST, PORT),
        Handler,
    ).serve_forever()
