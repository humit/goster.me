#!/usr/bin/env python3

from __future__ import annotations

import html
import io
import os
import re

from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse

import segno

import public_app as legacy

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

SHORT_CODE_RE = re.compile(
    rf"^[{re.escape(SHORT_CODE_ALPHABET)}]"
    rf"{{{SHORT_CODE_LENGTH}}}$"
)


def escape(value: str | None) -> str:
    return html.escape(value or "", quote=True)


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
<meta name="theme-color" content="#0b0d10">
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
    return product_document(
        "goster.me",
        """
<main class="product-home product-home-minimal">
    <section class="minimal-shell" aria-labelledby="home-title">
        <h1 id="home-title" class="minimal-wordmark">goster.me</h1>

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
                required
                autofocus
            >
            <button class="url-submit" type="submit">Göster</button>
        </form>

        <nav class="minimal-links" aria-label="Bilgi">
            <a href="/about">Hakkında</a>
            <a href="https://github.com/humit/goster.me/issues" rel="noopener noreferrer" target="_blank">İletişim</a>
        </nav>
    </section>
</main>
""",
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

        <p class="info-source">
            <a href="https://github.com/humit/goster.me" rel="noopener noreferrer" target="_blank">
                Kaynak kodu GitHub'da gör ↗
            </a>
        </p>
    </article>
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


def absolute_short_url(handler, code: str) -> str:
    forwarded_proto = handler.headers.get("X-Forwarded-Proto", "").split(",")[0].strip()
    scheme = forwarded_proto or "http"
    host = handler.headers.get("Host") or f"{HOST}:{PORT}"
    return f"{scheme}://{host}/{code}"


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


class Handler(legacy.Handler):
    server_version = "GosterMe/0.3"

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

        if path == "/about":
            self.send_html(200, render_about())
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
                item = STORE.get(code)

                if item is None:
                    self.send_html(410, render_expired(code))
                    return

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
        # legacy.Handler uses the monkey-patched save_item() and persists the
        # resolved item. Its /g/<code> redirect is canonicalized by do_GET().
        super().do_POST()


def ttl_days() -> float:
    return DEFAULT_TTL_SECONDS / (24 * 60 * 60)


if __name__ == "__main__":
    purged = STORE.purge_expired()

    print(
        f"goster.me listening on http://{HOST}:{PORT} "
        f"(short={SHORT_CODE_LENGTH}, ttl={ttl_days():g}d, purged={purged})",
        flush=True,
    )

    ThreadingHTTPServer(
        (HOST, PORT),
        Handler,
    ).serve_forever()
