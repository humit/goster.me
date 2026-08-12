#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import hmac
import html
import io
import json
import os
import re
import secrets
import threading
import time

from collections import OrderedDict, deque
from datetime import datetime, timedelta, timezone
from http.server import ThreadingHTTPServer
from ipaddress import ip_address
from pathlib import Path
from urllib.parse import parse_qs, urlparse

import segno

import adapters
import public_app as legacy

from analytics import AnalyticsStore, clean_campaign
from feedback import FeedbackStore, MESSAGE_MAX_LENGTH, normalize_submission
from unsupported import UnsupportedTargetStore

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
ANALYTICS = AnalyticsStore(STORE.path)
FEEDBACK = FeedbackStore(STORE.path)
UNSUPPORTED = UnsupportedTargetStore(STORE.path)
ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
PUBLIC_ORIGIN = public_origin()
MAX_POST_BYTES = int(os.environ.get("GOSTER_MAX_POST_BYTES", "4096"))
RESOLVE_RATE_PER_MINUTE = int(
    os.environ.get("GOSTER_RESOLVE_RATE_PER_MINUTE", "12")
)
TRUST_PROXY = os.environ.get("GOSTER_TRUST_PROXY", "0") == "1"
MAX_RATE_CLIENTS = int(os.environ.get("GOSTER_MAX_RATE_CLIENTS", "10000"))
FEEDBACK_RATE_PER_HOUR = int(
    os.environ.get("GOSTER_FEEDBACK_RATE_PER_HOUR", "5")
)
MAX_FEEDBACK_POST_BYTES = int(
    os.environ.get("GOSTER_MAX_FEEDBACK_POST_BYTES", "4096")
)
FEEDBACK_FORM_TOKEN_TTL_SECONDS = 60 * 60

SHORT_CODE_RE = re.compile(
    rf"^[{re.escape(SHORT_CODE_ALPHABET)}]"
    rf"{{{SHORT_CODE_LENGTH}}}$"
)

_rate_lock = threading.Lock()
_rate_clients: OrderedDict[str, deque[float]] = OrderedDict()
_feedback_rate_clients: OrderedDict[str, deque[float]] = OrderedDict()
_feedback_form_key = secrets.token_bytes(32)

_ORIGINAL_FETCH_HTML = adapters.fetch_html
_ORIGINAL_YOUTUBE_VIDEO_ID = adapters.YouTubeAdapter.video_id
_ORIGINAL_RESOLVE_URL = legacy.resolve_url


def escape(value: str | None) -> str:
    return html.escape(value or "", quote=True)


def issue_feedback_form_token(*, now: int | None = None) -> str:
    issued_at = int(time.time() if now is None else now)
    payload = f"{issued_at}.{secrets.token_urlsafe(18)}"
    signature = hmac.new(
        _feedback_form_key,
        payload.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return f"{payload}.{signature}"


def valid_feedback_form_token(token: str, *, now: int | None = None) -> bool:
    if len(token) > 128:
        return False
    try:
        issued_text, nonce, signature = token.split(".")
        issued_at = int(issued_text)
    except (TypeError, ValueError):
        return False
    if not re.fullmatch(r"[A-Za-z0-9_-]{20,32}", nonce):
        return False
    if not re.fullmatch(r"[0-9a-f]{64}", signature):
        return False

    checked_at = int(time.time() if now is None else now)
    age = checked_at - issued_at
    if age < -60 or age > FEEDBACK_FORM_TOKEN_TTL_SECONDS:
        return False

    payload = f"{issued_text}.{nonce}"
    expected = hmac.new(
        _feedback_form_key,
        payload.encode("ascii"),
        hashlib.sha256,
    ).hexdigest()
    return hmac.compare_digest(signature, expected)


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

    # Third-party source HTML/JavaScript must never execute under the primary
    # goster.me origin. Native/isolate content remains fail-closed until it
    # has a dedicated sandbox origin.
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

PUBLIC_META_DESCRIPTION = (
    "Bağlantılardaki video ve etkinlikleri gereksiz gezinme, reklam ve "
    "dikkat dağıtıcı öğelerden ayırarak gösterir."
)


def canonical_url(path: str) -> str:
    return f"{PUBLIC_ORIGIN}{path}"


def robots_text() -> str:
    return "\n".join(
        (
            "User-agent: *",
            "Allow: /",
            "Disallow: /q/",
            "Disallow: /qr/",
            "Disallow: /g/",
            "Disallow: /v/",
            "Disallow: /resolve",
            "Disallow: /api/",
            "Disallow: /contact/thanks",
            f"Sitemap: {canonical_url('/sitemap.xml')}",
            "",
        )
    )


def sitemap_xml() -> str:
    urls = ("/", "/about", "/contact")
    entries = "\n".join(
        f"  <url><loc>{escape(canonical_url(path))}</loc></url>" for path in urls
    )
    return (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        f"{entries}\n"
        "</urlset>\n"
    )


def security_text(*, now: datetime | None = None) -> str:
    current = now or datetime.now(timezone.utc)
    expires = current + timedelta(days=180)
    return "\n".join(
        (
            f"Contact: {canonical_url('/contact')}",
            f"Expires: {expires.strftime('%Y-%m-%dT%H:%M:%SZ')}",
            "Preferred-Languages: tr, en",
            f"Canonical: {canonical_url('/.well-known/security.txt')}",
            "Policy: https://github.com/humit/goster.me/blob/main/docs/SECURITY_ARCHITECTURE.md",
            "",
        )
    )


def robots_directive_for_target(target: str) -> str | None:
    parsed = urlparse(target)
    path = parsed.path
    parts = [part for part in path.split("/") if part]
    dynamic_route = (
        path in {"/resolve", "/contact/thanks"}
        or (path == "/contact" and bool(parsed.query))
        or path.startswith("/api/")
        or (len(parts) == 2 and parts[0] in {"q", "qr", "g", "v"})
        or (len(parts) == 1 and SHORT_CODE_RE.fullmatch(parts[0].lower()))
    )
    if dynamic_route:
        return "noindex, nofollow, noarchive"
    return None


def product_document(
    title: str,
    body: str,
    *,
    description: str | None = None,
    canonical_path: str | None = None,
) -> str:
    """Shared HTML shell.

    Presentation lives in static/product.css and behavior in static/product.js
    so contributors can work on UI without editing the Python renderer.
    """
    return f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0b0d10">
<title>{escape(title)}</title>
{f'<meta name="description" content="{escape(description)}">' if description else ''}
{f'<link rel="canonical" href="{escape(canonical_url(canonical_path))}">' if canonical_path else ''}
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


def render_home(campaign: str | None = None) -> str:
    action = "/resolve"
    if campaign:
        action += f"?campaign={escape(campaign)}"

    return product_document(
        "goster.me",
        f"""
<main class="product-home product-home-minimal">
    <section class="minimal-shell" aria-labelledby="home-title">
        <h1 id="home-title" class="minimal-wordmark">goster.me</h1>

        <form class="url-form product-url-form" method="post" action="{action}">
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

        <nav class="minimal-links" aria-label="Bilgi">
            <a href="/about">Hakkında</a>
            <a href="/contact">İletişim</a>
        </nav>
    </section>
</main>
""",
        description=PUBLIC_META_DESCRIPTION,
        canonical_path="/",
    )


def render_about() -> str:
    return product_document(
        "Hakkında — goster.me",
        """
<main class="info-page">
    <header class="info-header">
        <a class="product-wordmark" href="/">goster.me</a>
        <a class="text-link" href="/">← Geri</a>
    </header>

    <article class="info-content">
        <h1>İçeriği göster. Gerisini gösterme.</h1>
        <p class="info-lead">
            goster.me, bir bağlantının içindeki asıl içeriği ayıklayıp gereksiz
            sayfa kalabalığını mümkün olduğunca geride bırakır.
        </p>

        <section>
            <h2>Neden?</h2>
            <p>
                Bir videoyu, oyunu, ödevi ya da etkinliği görmek; reklamları,
                önerileri, otomatik oynatmayı ve dikkat dağıtıcı arayüzleri de
                görmek zorunda olmak demek değildir.
            </p>
        </section>

        <section id="how">
            <h2>Nasıl çalışır?</h2>
            <ol>
                <li>Kaynak bağlantıyı yapıştırırsın.</li>
                <li>goster.me desteklediği içeriği tanır ve ayıklar.</li>
                <li>Yalnızca gerekli içeriği kısa bir adreste gösterir.</li>
            </ol>
        </section>

        <section>
            <h2>Desteklenen içerikler</h2>
            <p>
                YouTube videoları, Wordwall etkinlikleri ve desteklenen eğitim
                sitelerindeki belirli interaktif içerikler. Destek yeni gerçek
                bağlantılar üzerinden genişletilir.
            </p>
        </section>

        <section>
            <h2>Mahremiyet</h2>
            <p>
                Ürünün çalışıp çalışmadığını anlamak için sayfa ve işlem türleri
                ölçülür. Çerez, reklam ağı veya üçüncü taraf analytics kullanılmaz.
                Ham IP adresi saklanmaz; tekrarları yaklaşık sayabilmek için günlük
                değişen korumalı bir etiket üretilir. Ham ölçüm kayıtları 30 gün
                sonra silinir.
            </p>
        </section>

        <p class="info-source">
            <a href="https://github.com/humit/goster.me" rel="noopener noreferrer" target="_blank">
                Kaynak kodu GitHub'da gör ↗
            </a>
        </p>
    </article>
</main>
""",
        description="goster.me'nin içerik sadeleştirme, güvenlik ve mahremiyet yaklaşımı.",
        canonical_path="/about",
    )


def render_contact(
    *,
    category: str = "problem",
    message: str = "",
    error: str = "",
) -> str:
    form_token = issue_feedback_form_token()
    options = []
    for value, label in (
        ("problem", "Bir sorun bildirmek istiyorum"),
        ("suggestion", "Bir önerim var"),
        ("other", "Başka bir konu"),
    ):
        selected = " selected" if value == category else ""
        options.append(f'<option value="{value}"{selected}>{label}</option>')

    error_html = (
        f'<p class="form-error" role="alert">{escape(error)}</p>'
        if error
        else ""
    )
    return product_document(
        "İletişim — goster.me",
        f"""
<main class="contact-page">
    <header class="info-header">
        <a class="product-wordmark" href="/">goster.me</a>
        <a class="text-link" href="/">← Geri</a>
    </header>

    <section class="contact-content" aria-labelledby="contact-title">
        <h1 id="contact-title">Mesaj bırak</h1>
        <p class="contact-lead">
            Karşılaştığınız sorunu veya önerinizi yazabilirsiniz. Mesajınız
            herkese açık olmaz.
        </p>
        {error_html}
        <form class="contact-form" method="post" action="/contact">
            <input type="hidden" name="form_token" value="{form_token}">

            <label for="category">Konu</label>
            <select id="category" name="category" required>
                {''.join(options)}
            </select>

            <label for="message">Mesajınız</label>
            <textarea
                id="message"
                name="message"
                rows="7"
                minlength="3"
                maxlength="{MESSAGE_MAX_LENGTH}"
                required
            >{escape(message)}</textarea>

            <div class="form-trap" aria-hidden="true">
                <label for="website">Web sitesi</label>
                <input id="website" name="website" type="text" tabindex="-1" autocomplete="off">
            </div>
            <button type="submit">Mesajı gönder</button>
        </form>
    </section>
</main>
""",
        description="goster.me için sorun bildirimi ve ürün önerisi iletişim formu.",
        canonical_path="/contact",
    )


def render_feedback_received() -> str:
    return product_document(
        "Mesajınız alındı — goster.me",
        """
<main class="contact-page">
    <header class="info-header">
        <a class="product-wordmark" href="/">goster.me</a>
        <a class="text-link" href="/">← Ana sayfa</a>
    </header>
    <section class="contact-content">
        <h1>Mesajınız alındı.</h1>
        <p class="contact-lead">Paylaştığınız geri bildirim için teşekkürler.</p>
        <a class="contact-return" href="/">Ana sayfaya dön</a>
    </section>
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
            title="Bağlantıyı kopyala"
        >Kopyala</button>
        <button
            class="viewer-action"
            type="button"
            data-action="share"
            data-url="{canonical}"
            aria-label="Paylaş"
            title="Paylaş"
        >Paylaş</button>
        <a
            class="viewer-action"
            href="/q/{escape(item_id)}"
            data-action="qr"
            aria-label="QR kodu göster"
            title="QR kodu göster"
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


def allow_feedback(client: str) -> bool:
    if FEEDBACK_RATE_PER_HOUR <= 0:
        return True

    now = time.monotonic()
    cutoff = now - 3600.0

    with _rate_lock:
        bucket = _feedback_rate_clients.get(client)
        if bucket is None:
            if len(_feedback_rate_clients) >= MAX_RATE_CLIENTS:
                _feedback_rate_clients.popitem(last=False)
            bucket = deque()
            _feedback_rate_clients[client] = bucket
        else:
            _feedback_rate_clients.move_to_end(client)

        while bucket and bucket[0] <= cutoff:
            bucket.popleft()
        if len(bucket) >= FEEDBACK_RATE_PER_HOUR:
            return False
        bucket.append(now)
        return True


def same_origin_request(handler) -> bool:
    fetch_site = handler.headers.get("Sec-Fetch-Site", "")
    # Modern browsers provide Sec-Fetch-Site as a non-script-writable CSRF
    # signal. Prefer an explicit same-origin value because privacy settings can
    # serialize the separate Origin header as the literal value "null".
    if fetch_site == "same-origin":
        return True
    if fetch_site and fetch_site != "none":
        return False
    origin = handler.headers.get("Origin")
    return origin is None or origin.rstrip("/") == PUBLIC_ORIGIN.rstrip("/")


class Handler(legacy.Handler):
    server_version = "GosterMe/0.4"

    def is_head_request(self) -> bool:
        return getattr(self, "command", "GET") == "HEAD"

    def end_headers(self) -> None:
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Referrer-Policy", "no-referrer")
        self.send_header("X-Frame-Options", "DENY")
        robots = robots_directive_for_target(getattr(self, "path", ""))
        if robots:
            self.send_header("X-Robots-Tag", robots)
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
        if not self.is_head_request():
            self.wfile.write(value)

    def send_html(self, status: int, value: str) -> None:
        self.send_bytes(
            status,
            value.encode("utf-8"),
            "text/html; charset=utf-8",
        )

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

        if path == "/robots.txt" and not parsed.query:
            self.send_bytes(
                200,
                robots_text().encode("utf-8"),
                "text/plain; charset=utf-8",
                cache_control="public, max-age=3600",
            )
            return

        if path == "/sitemap.xml" and not parsed.query:
            self.send_bytes(
                200,
                sitemap_xml().encode("utf-8"),
                "application/xml; charset=utf-8",
                cache_control="public, max-age=3600",
            )
            return

        if path == "/.well-known/security.txt" and not parsed.query:
            self.send_bytes(
                200,
                security_text().encode("utf-8"),
                "text/plain; charset=utf-8",
                cache_control="public, max-age=3600",
            )
            return

        if path == "/":
            query = parse_qs(parsed.query, keep_blank_values=True)
            campaign = None
            if set(query).issubset({"from"}) and len(query.get("from", [])) <= 1:
                campaign = clean_campaign((query.get("from") or [None])[0])
            if not self.is_head_request():
                ANALYTICS.record(
                    "landing_view",
                    campaign=campaign,
                    visitor_ip=client_ip(self),
                )
            self.send_html(200, render_home(campaign))
            return

        if path == "/about":
            if not self.is_head_request():
                ANALYTICS.record("about_view", visitor_ip=client_ip(self))
            self.send_html(200, render_about())
            return

        if path == "/contact" and not parsed.query:
            if not self.is_head_request():
                ANALYTICS.record("contact_view", visitor_ip=client_ip(self))
            self.send_html(200, render_contact())
            return

        if path == "/contact/thanks" and not parsed.query:
            self.send_html(200, render_feedback_received())
            return

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

                if not self.is_head_request():
                    ANALYTICS.record(
                        "share_page_view",
                        provider=item.provider,
                        adapter=item.adapter,
                        render_mode=item.render_mode,
                        visitor_ip=client_ip(self),
                    )
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

                if not self.is_head_request():
                    # Count only content that is actually served.
                    item = STORE.get(code)
                    ANALYTICS.record(
                        "viewer_open",
                        provider=item.provider,
                        adapter=item.adapter,
                        render_mode=item.render_mode,
                        visitor_ip=client_ip(self),
                    )
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

    def do_HEAD(self) -> None:
        self.do_GET()

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path == "/api/events" and not parsed.query:
            self.handle_product_event()
            return

        if parsed.path == "/contact" and not parsed.query:
            self.handle_feedback()
            return

        if parsed.path != "/resolve":
            self.send_error(404)
            return

        query = parse_qs(parsed.query, keep_blank_values=True)
        if not set(query).issubset({"campaign"}) or len(query.get("campaign", [])) > 1:
            self.send_error(404)
            return
        campaign = clean_campaign((query.get("campaign") or [None])[0])

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

        validated_url = None
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
            validated_url = url
            ANALYTICS.record(
                "resolve_attempt", campaign=campaign, visitor_ip=client_ip(self)
            )
            item = hardened_resolve_url(url)
            item_id = save_item(item)

        except (ValueError, SecurityValidationError, adapters.AdapterError):
            if validated_url is not None:
                try:
                    UNSUPPORTED.record(validated_url)
                except Exception:
                    self.log_error("unsupported target recording failed")
            ANALYTICS.record(
                "resolve_failure", campaign=campaign, outcome="unsupported",
                visitor_ip=client_ip(self),
            )
            self.send_html(
                400,
                render_security_error(
                    "Bağlantı desteklenmiyor",
                    "Bu bağlantı güvenli biçimde işlenemedi veya henüz desteklenmiyor.",
                ),
            )
            return

        except Exception as exc:
            ANALYTICS.record(
                "resolve_failure", campaign=campaign, outcome="internal",
                visitor_ip=client_ip(self),
            )
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

        ANALYTICS.record(
            "resolve_success",
            campaign=campaign,
            provider=item.provider,
            adapter=item.adapter,
            render_mode=item.render_mode,
            visitor_ip=client_ip(self),
        )
        self.redirect(f"/{item_id}")

    def handle_feedback(self) -> None:
        content_type = self.headers.get("Content-Type", "")
        media_type = content_type.split(";", 1)[0].strip().lower()
        if media_type != "application/x-www-form-urlencoded":
            self.send_error(415)
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > MAX_FEEDBACK_POST_BYTES:
            self.send_error(400)
            return

        category = "problem"
        message = ""
        website = ""
        try:
            raw = self.rfile.read(length).decode("utf-8", errors="strict")
            data = parse_qs(
                raw,
                keep_blank_values=True,
                strict_parsing=True,
                max_num_fields=6,
            )
            if set(data) != {"category", "message", "website", "form_token"}:
                raise ValueError("Unexpected form fields.")
            if any(len(values) != 1 for values in data.values()):
                raise ValueError("Repeated form fields.")

            category = data["category"][0]
            message = data["message"][0]
            website = data["website"][0]
        except (UnicodeError, ValueError):
            self.send_html(
                400,
                render_contact(
                    category=(
                        category
                        if category in {"problem", "suggestion", "other"}
                        else "problem"
                    ),
                    message=message[:MESSAGE_MAX_LENGTH],
                    error="Mesaj gönderilemedi. Alanları kontrol edip yeniden deneyin.",
                ),
            )
            return

        # A filled honeypot gets the same response as a real submission so
        # automated senders do not learn how to bypass it.
        if website:
            self.redirect("/contact/thanks")
            return

        if not same_origin_request(self) and not valid_feedback_form_token(
            data["form_token"][0]
        ):
            self.send_error(403)
            return

        if not allow_feedback(client_ip(self)):
            self.send_response(429)
            self.send_header("Retry-After", "3600")
            self.send_header("Content-Length", "0")
            self.end_headers()
            return

        try:
            normalized_category, normalized_message = normalize_submission(
                category, message, website
            )
            FEEDBACK.submit(normalized_category, normalized_message)
        except ValueError:
            self.send_html(
                400,
                render_contact(
                    category=(
                        category
                        if category in {"problem", "suggestion", "other"}
                        else "problem"
                    ),
                    message=message[:MESSAGE_MAX_LENGTH],
                    error="Mesaj gönderilemedi. Alanları kontrol edip yeniden deneyin.",
                ),
            )
            return
        except Exception as exc:
            request_id = f"{int(time.time()):x}-{threading.get_ident():x}"
            self.log_error("feedback failed request_id=%s error=%r", request_id, exc)
            self.send_html(
                500,
                render_security_error(
                    "Bir sorun oluştu",
                    f"Mesaj kaydedilemedi. Hata kodu: {request_id}",
                ),
            )
            return

        ANALYTICS.record("feedback_submitted", visitor_ip=client_ip(self))
        # Post/Redirect/Get prevents a browser refresh from duplicating a message.
        self.redirect("/contact/thanks")

    def handle_product_event(self) -> None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            length = 0
        if length <= 0 or length > 256:
            self.send_error(400)
            return
        if self.headers.get("Content-Type", "").split(";", 1)[0].strip().lower() != "application/json":
            self.send_error(415)
            return
        try:
            payload = json.loads(self.rfile.read(length).decode("utf-8", errors="strict"))
            if not isinstance(payload, dict) or set(payload) != {"event", "code"}:
                raise ValueError
            event = payload["event"]
            code = payload["code"]
            if event not in {"copy_click", "share_click"} or not isinstance(code, str):
                raise ValueError
            item = STORE.get(code, touch=False)
            if item is None:
                raise ValueError
            ANALYTICS.record(
                event,
                provider=item.provider,
                adapter=item.adapter,
                render_mode=item.render_mode,
                visitor_ip=client_ip(self),
            )
        except (UnicodeError, ValueError, json.JSONDecodeError):
            self.send_error(400)
            return
        self.send_response(204)
        self.send_header("Content-Length", "0")
        self.end_headers()


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
