#!/usr/bin/env python3

from __future__ import annotations

import html
import os
import random
import re
import time

from http.server import ThreadingHTTPServer
from urllib.parse import urlparse

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


def escape(value: str | None) -> str:
    return html.escape(value or "", quote=True)


def save_item(item):
    return STORE.save(item)


def get_item(item_id: str):
    return STORE.get(item_id)


# Existing renderer functions resolve these names from public_app's module
# globals, so replacing them lets the tested renderer gain persistence without
# copying or forking adapter/rendering logic.
legacy.save_item = save_item
legacy.get_item = get_item


def public_url(code: str) -> str:
    return f"/{escape(code)}"


def render_home() -> str:
    slogan = random.choice(SLOGANS)

    return legacy.document(
        "goster.me — Gerekmeyeni gösterme",
        f"""
<main class="home product-home">
    <header class="product-header">
        <a class="product-wordmark" href="/" aria-label="goster.me ana sayfa">
            goster.me
        </a>
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
            önerileri, otomatik oynatmayı, karmaşık menüleri ve gereksiz sayfa
            kalabalığını da görmek zorunda değiliz. Özellikle çocuklarımız için.
        </p>
    </section>

    <footer class="product-footer">
        <span>Kısa adres. Temiz içerik. Daha az dikkat dağıtıcı.</span>
        <a href="https://github.com/humit/goster.me" rel="noopener noreferrer" target="_blank">
            Açık kaynak ↗
        </a>
    </footer>
</main>

<style>
/* Product shell intentionally stays quiet: the content is the product. */
.product-home {{
    width: min(100%, 760px);
    justify-content: flex-start;
    gap: 0;
    padding-top: max(26px, env(safe-area-inset-top));
}}

.product-header {{
    display: flex;
    align-items: center;
    min-height: 44px;
    margin-bottom: clamp(54px, 10vh, 100px);
}}

.product-wordmark {{
    color: var(--text);
    text-decoration: none;
    font-size: 20px;
    font-weight: 850;
    letter-spacing: -.04em;
}}

.hero {{
    max-width: 700px;
}}

.eyebrow {{
    margin: 0 0 15px;
    color: var(--accent);
    font-size: 13px;
    font-weight: 750;
    letter-spacing: .08em;
    text-transform: uppercase;
}}

.product-home h1 {{
    max-width: 690px;
    margin-bottom: 20px;
    font-size: clamp(42px, 8vw, 72px);
    line-height: .98;
}}

.domain-punch {{
    color: var(--accent-strong);
}}

.hero-copy {{
    max-width: 580px;
    margin: 0 0 28px;
    color: #cbd5e1;
    font-size: clamp(17px, 2.5vw, 20px);
    line-height: 1.55;
}}

.product-url-form {{
    max-width: 680px;
}}

.current-slogan {{
    min-height: 22px;
    margin: 16px 4px 0;
    color: var(--muted);
    font-size: 14px;
}}

.manifesto {{
    max-width: 680px;
    margin-top: clamp(72px, 12vh, 120px);
    padding-top: 28px;
    border-top: 1px solid rgba(148, 163, 184, .18);
}}

.manifesto h2 {{
    margin: 0 0 18px;
    font-size: 14px;
    color: var(--muted);
    text-transform: uppercase;
    letter-spacing: .08em;
}}

.manifesto p {{
    max-width: 640px;
    margin: 0 0 14px;
    color: var(--muted);
    font-size: 15px;
    line-height: 1.65;
}}

.manifesto .manifesto-lead {{
    color: var(--text);
    font-size: clamp(20px, 3vw, 25px);
    line-height: 1.45;
    letter-spacing: -.015em;
}}

.product-footer {{
    margin-top: 70px;
    padding: 22px 0 4px;
    border-top: 1px solid rgba(148, 163, 184, .12);
    display: flex;
    justify-content: space-between;
    gap: 18px;
    color: #64748b;
    font-size: 12px;
}}

.product-footer a {{
    color: var(--muted);
    text-decoration: none;
}}

@media (max-width: 520px) {{
    .product-header {{
        margin-bottom: 52px;
    }}

    .product-home h1 {{
        font-size: clamp(40px, 12vw, 58px);
    }}

    .product-footer {{
        flex-direction: column;
    }}
}}
</style>
""",
    )


def branded_preview_actions(
    item_id: str,
    *,
    back_href: str = "/",
) -> str:
    return f"""
<div class="viewer-toolbar product-viewer-toolbar">
    <div class="viewer-toolbar-group product-viewer-left">
        <a
            class="viewer-icon"
            href="{escape(back_href)}"
            aria-label="Geri dön"
            title="Geri dön"
        >←</a>
        <a class="viewer-brand" href="/" aria-label="goster.me ana sayfa">goster.me</a>
    </div>

    <div class="viewer-toolbar-group product-viewer-actions">
        <button id="viewer-copy" class="viewer-text-action" type="button">Kopyala</button>
        <button id="viewer-share" class="viewer-text-action" type="button">Paylaş</button>
    </div>
</div>

<style>
.product-viewer-left {{
    align-items: center;
}}

.viewer-brand,
.viewer-text-action {{
    min-height: 42px;
    display: inline-flex;
    align-items: center;
    border: 1px solid rgba(255,255,255,.18);
    background: rgba(10,15,28,.84);
    color: #fff;
    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);
    box-shadow: 0 4px 18px rgba(0,0,0,.18);
}}

.viewer-brand {{
    padding: 0 13px;
    border-radius: 999px;
    text-decoration: none;
    font-size: 13px;
    font-weight: 800;
    letter-spacing: -.03em;
}}

.viewer-text-action {{
    padding: 0 13px;
    border-radius: 999px;
    font-size: 13px;
    font-weight: 750;
    cursor: pointer;
}}

@media (max-width: 430px) {{
    .viewer-brand {{
        display: none;
    }}

    .viewer-text-action {{
        width: 42px;
        padding: 0;
        overflow: hidden;
        color: transparent;
        position: relative;
    }}

    #viewer-copy::after {{
        content: "⧉";
    }}

    #viewer-share::after {{
        content: "↗";
    }}

    .viewer-text-action::after {{
        position: absolute;
        inset: 0;
        display: grid;
        place-items: center;
        color: #fff;
        font-size: 18px;
    }}
}}
</style>

<script>
(() => {{
    const cleanUrl = location.origin + "/{escape(item_id)}";
    const copy = document.getElementById("viewer-copy");
    const share = document.getElementById("viewer-share");

    async function copyCleanUrl(button) {{
        await navigator.clipboard.writeText(cleanUrl);
        const old = button.textContent;
        button.textContent = "Kopyalandı ✓";
        setTimeout(() => button.textContent = old, 1200);
    }}

    copy?.addEventListener("click", () => copyCleanUrl(copy));

    share?.addEventListener("click", async () => {{
        if (navigator.share) {{
            try {{
                await navigator.share({{ url: cleanUrl }});
                return;
            }} catch (_) {{}}
        }}
        await copyCleanUrl(share);
    }});
}})();
</script>
"""


legacy.render_home = render_home
legacy.preview_actions = branded_preview_actions


class Handler(legacy.Handler):
    server_version = "GosterMe/0.2"

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        parts = [part for part in path.split("/") if part]

        # Canonical public form: goster.me/abc346
        if len(parts) == 1:
            code = parts[0].lower()

            if SHORT_CODE_RE.fullmatch(code):
                item = STORE.get(code)

                if item is None:
                    self.send_html(
                        410,
                        render_expired(code),
                    )
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
        # legacy.Handler uses the monkey-patched save_item() and therefore
        # persists the resolved item. Its final /g/<code> redirect is retained
        # only for one hop; do_GET above canonicalizes it to /<code>.
        super().do_POST()


def render_expired(code: str) -> str:
    return legacy.document(
        "Bağlantının süresi doldu",
        f"""
<main class="home">
    <a class="product-wordmark" href="/">goster.me</a>
    <h1>Bu bağlantının süresi doldu.</h1>
    <p class="subtitle">
        Kısa bağlantılar geçicidir. Kaynak bağlantı elindeyse yeniden
        goster.me ve yeni bir kısa adres oluştur.
    </p>
    <div class="actions">
        <a class="button" href="/">Yeni bağlantı oluştur</a>
    </div>
    <p class="source">Kod: {escape(code)}</p>
</main>
""",
    )


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
