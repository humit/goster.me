#!/usr/bin/env python3

from __future__ import annotations

import html
import json
import os
import secrets
import threading

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
from urllib.request import Request, urlopen

from adapters import (
    AdapterError,
    ResolvedContent,
    fetch_html,
    hostname,
    resolve_url,
)


HOST = os.environ.get(
    "GOSTER_HOST",
    "0.0.0.0",
)

PORT = int(
    os.environ.get(
        "GOSTER_PORT",
        "8090",
    )
)

items: dict[str, ResolvedContent] = {}
items_lock = threading.Lock()


def escape(value: str | None) -> str:
    return html.escape(value or "", quote=True)


def clean_title(value: str | None) -> str:
    if not value:
        return "Etkinlik"

    suffixes = (
        " | ilk-okul.com",
        " – İlkokul Evim | İlkokul Ders İçerikleri, Deneme ve Tarama Sınavları, Bilgi Yarışmaları...",
    )

    result = value.strip()

    for suffix in suffixes:
        if result.endswith(suffix):
            result = result[: -len(suffix)].strip()

    return result or "Etkinlik"


def new_id() -> str:
    while True:
        value = secrets.token_urlsafe(5).replace("-", "").replace("_", "")

        if len(value) < 6:
            continue

        with items_lock:
            if value not in items:
                return value


def save_item(item: ResolvedContent) -> str:
    item_id = new_id()

    with items_lock:
        items[item_id] = item

    return item_id


def get_item(item_id: str) -> ResolvedContent | None:
    with items_lock:
        return items.get(item_id)


BASE_STYLE = """
<style>
:root {
    font-family:
        Inter,
        ui-sans-serif,
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;

    color-scheme: dark;

    --bg: #0b1020;
    --surface: #121a2d;
    --surface-2: #182238;
    --border: #26334d;

    --text: #f8fafc;
    --muted: #94a3b8;

    --accent: #7dd3fc;
    --accent-strong: #38bdf8;

    --success: #86efac;
    --danger: #fca5a5;
}

* {
    box-sizing: border-box;
}

html,
body {
    margin: 0;
    min-height: 100%;
    background:
        radial-gradient(
            circle at top,
            #172554 0,
            var(--bg) 340px
        );
    color: var(--text);
}

body {
    min-height: 100vh;
    min-height: 100dvh;
}

main {
    width: min(100%, 680px);
    margin: 0 auto;

    padding:
        max(22px, env(safe-area-inset-top))
        18px
        max(32px, env(safe-area-inset-bottom));
}

.home {
    min-height: 100vh;
    min-height: 100dvh;

    display: flex;
    flex-direction: column;
    justify-content: center;

    padding-top:
        max(34px, env(safe-area-inset-top));
    padding-bottom:
        max(28px, env(safe-area-inset-bottom));
}

.brand {
    display: flex;
    align-items: center;
    gap: 11px;

    margin-bottom: 22px;
}

.brand-mark {
    width: 38px;
    height: 38px;

    display: grid;
    place-items: center;

    border-radius: 12px;

    background:
        linear-gradient(
            135deg,
            #38bdf8,
            #818cf8
        );

    color: #07111f;
    font-size: 21px;
    font-weight: 900;

    box-shadow:
        0 12px 30px
        rgba(56, 189, 248, .20);
}

.brand-name {
    font-weight: 850;
    letter-spacing: -.02em;
}

h1 {
    margin: 0 0 10px;

    font-size:
        clamp(28px, 8vw, 42px);

    line-height: 1.05;
    letter-spacing: -.035em;
}

.subtitle {
    margin: 0 0 22px;

    color: var(--muted);
    line-height: 1.5;
    font-size: 15px;
}

.supported-link {
    appearance: none;

    border: 0;
    padding: 0;

    min-height: auto;
    background: none;

    color: var(--accent);
    font-weight: 750;

    text-decoration:
        underline
        dotted
        rgba(125, 211, 252, .6);

    text-underline-offset: 4px;
}

.supported {
    margin: -8px 0 18px;

    border: 1px solid var(--border);
    border-radius: 14px;

    background:
        rgba(18, 26, 45, .75);

    overflow: hidden;
}

.supported summary {
    padding: 13px 15px;

    cursor: pointer;

    color: #dbeafe;
    font-size: 14px;
    font-weight: 750;

    list-style: none;
}

.supported summary::-webkit-details-marker {
    display: none;
}

.supported summary::after {
    content: "＋";
    float: right;

    color: var(--muted);
}

.supported[open] summary::after {
    content: "−";
}

.supported-content {
    padding:
        0
        15px
        14px;

    color: var(--muted);
    font-size: 13px;
    line-height: 1.55;
}

.site-chips {
    display: flex;
    flex-wrap: wrap;
    gap: 7px;

    margin-top: 10px;
}

.site-chip {
    padding: 6px 9px;

    border: 1px solid var(--border);
    border-radius: 999px;

    background: var(--surface-2);

    color: #dbeafe;

    font-size: 12px;
    font-weight: 650;
}

form {
    margin: 0;
}

label {
    position: absolute;

    width: 1px;
    height: 1px;

    overflow: hidden;
    clip: rect(0 0 0 0);
}

.url-form {
    display: grid;
    grid-template-columns:
        minmax(0, 1fr)
        auto;

    gap: 9px;

    padding: 7px;

    border:
        1px solid
        rgba(148, 163, 184, .22);

    border-radius: 18px;

    background:
        rgba(18, 26, 45, .92);

    box-shadow:
        0 18px 50px
        rgba(0, 0, 0, .22);
}

input,
button,
.button {
    font: inherit;
}

input {
    width: 100%;
    min-width: 0;

    height: 50px;

    border: 0;
    border-radius: 12px;

    padding: 0 12px;

    outline: none;

    background: transparent;
    color: #fff;

    font-size: 16px;
}

input::placeholder {
    color: #64748b;
}

input:focus {
    background:
        rgba(30, 41, 59, .72);
}

button,
.button {
    display: inline-flex;
    align-items: center;
    justify-content: center;

    min-height: 48px;

    border: 0;
    border-radius: 12px;

    padding: 0 17px;

    background: var(--accent-strong);
    color: #062033;

    font-weight: 850;

    text-decoration: none;
    cursor: pointer;
}

.url-submit {
    min-width: 92px;
}

.secondary {
    background: var(--surface-2);
    color: var(--text);

    border: 1px solid var(--border);
}

.home-footer {
    margin-top: 24px;

    display: flex;
    align-items: center;
    justify-content: space-between;

    gap: 12px;

    color: #64748b;

    font-size: 12px;
}

.home-footer a,
.text-link {
    color: var(--muted);
    text-decoration: none;
}

.home-footer a:hover,
.text-link:hover {
    color: var(--accent);
}

.suggest-box {
    margin-top: 12px;

    padding: 14px 15px;

    border:
        1px solid
        rgba(148, 163, 184, .16);

    border-radius: 14px;

    background:
        rgba(18, 26, 45, .48);

    color: var(--muted);

    font-size: 13px;
    line-height: 1.45;
}

.suggest-box strong {
    color: #e2e8f0;
}

.card {
    margin-top: 18px;
    padding: 18px;

    border: 1px solid var(--border);
    border-radius: 18px;

    background: var(--surface);
}

.actions {
    display: grid;
    gap: 10px;

    margin-top: 18px;
}

.status-ok {
    color: var(--success);
    font-weight: 700;
}

.status-error {
    color: var(--danger);
    font-weight: 700;
}

.activity-list {
    display: grid;
    gap: 10px;

    margin-top: 20px;
}

.activity {
    width: 100%;
    min-height: 76px;

    margin: 0;

    background:
        rgba(18, 26, 45, .9);

    color: var(--text);

    border: 1px solid var(--border);
    border-radius: 16px;

    padding: 14px 16px;

    text-align: left;

    display: flex;
    align-items: center;
    justify-content: space-between;

    text-decoration: none;
}

.activity strong {
    display: block;
    font-size: 17px;
}

.activity small {
    display: block;

    margin-top: 4px;

    color: var(--muted);
}

.arrow {
    color: var(--accent);
    font-size: 30px;
}

.source {
    margin-top: 20px;

    color: #64748b;
    font-size: 12px;

    overflow-wrap: anywhere;
}

.fullscreen-viewer {
    position: fixed;
    inset: 0;

    width: 100vw;
    height: 100vh;
    height: 100dvh;

    background: #fff;

    overflow: hidden;
}

.fullscreen-frame {
    position: absolute;
    inset: 0;

    width: 100%;
    height: 100%;

    min-height: 0;

    border: 0;
    background: #fff;
}

.viewer-toolbar {
    position: fixed;

    z-index: 2147483647;

    top:
        max(
            10px,
            env(safe-area-inset-top)
        );

    left:
        max(
            10px,
            env(safe-area-inset-left)
        );

    right:
        max(
            10px,
            env(safe-area-inset-right)
        );

    pointer-events: none;

    display: flex;
    justify-content: space-between;

    gap: 8px;
}

.viewer-toolbar-group {
    display: flex;
    gap: 7px;

    pointer-events: auto;
}

.viewer-icon {
    width: 42px;
    height: 42px;
    min-height: 42px;

    padding: 0;

    border:
        1px solid
        rgba(255, 255, 255, .18);

    border-radius: 50%;

    background:
        rgba(10, 15, 28, .82);

    color: #fff;

    backdrop-filter: blur(12px);
    -webkit-backdrop-filter: blur(12px);

    box-shadow:
        0 4px 18px
        rgba(0, 0, 0, .22);

    font-size: 19px;
    line-height: 1;

    text-decoration: none;
}

.viewer-icon:hover {
    background:
        rgba(15, 23, 42, .96);
}

.youtube-frame,
.youtube-frame iframe {
    position: absolute;
    inset: 0;

    width: 100% !important;
    height: 100% !important;

    min-height: 0 !important;

    border: 0;
    background: #000;
}

.youtube-player-frame {
    position: absolute;
    inset: 0;

    display: block;

    width: 100%;
    height: 100%;

    min-height: 0;

    border: 0;
    background: #000;
}

.youtube-finished {
    position: fixed;
    z-index: 2147483646;
    inset: 0;

    background: #000;
    color: #fff;
}

.youtube-finished[hidden] {
    display: none;
}

.youtube-finished-card {
    width: min(90%, 420px);

    position: absolute;
    top: 50%;
    left: 50%;

    transform:
        translate(-50%, -50%);

    text-align: center;
}

.youtube-finished-card strong {
    display: block;

    margin-bottom: 22px;

    font-size: 24px;
}

.youtube-finished-card button,
.youtube-finished-card .button {
    width: 100%;
    margin: 8px 0;
}

.collection-head {
    display: flex;
    align-items: flex-start;
    justify-content: space-between;

    gap: 12px;
}

.collection-actions {
    display: flex;
    gap: 7px;

    flex-shrink: 0;
}

.collection-actions .viewer-icon {
    position: static;
}

@media (max-width: 520px) {
    .home {
        justify-content: flex-start;

        padding-top:
            max(
                56px,
                env(safe-area-inset-top)
            );
    }

    .url-form {
        grid-template-columns: 1fr;
    }

    .url-submit {
        width: 100%;
    }

    .home-footer {
        align-items: flex-start;
        flex-direction: column;
    }
}
</style>
"""




def document(title: str, body: str) -> str:
    return f"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<meta
    name="viewport"
    content="width=device-width,initial-scale=1,viewport-fit=cover"
>
<meta name="theme-color" content="#111827">
<title>{escape(title)}</title>
{BASE_STYLE}
</head>
<body>
{body}
</body>
</html>
"""


def render_home() -> str:
    return document(
        "Göster",
        """
<main class="home">
    <div class="brand">
        <div
            class="brand-mark"
            aria-hidden="true"
        >
            G
        </div>

        <div class="brand-name">
            goster.me
        </div>
    </div>

    <h1>
        Bağlantıyı sadeleştir.
    </h1>

    <p class="subtitle">
        <button
            id="supported-toggle"
            class="supported-link"
            type="button"
        >
            Desteklenen
        </button>
        bir bağlantı yapıştırın.
        Çocuk için gerekli içeriği mümkün olduğunca
        kaynak sitenin geri kalanından ayıralım.
    </p>

    <details
        id="supported"
        class="supported"
    >
        <summary>
            Desteklenen siteler
        </summary>

        <div class="supported-content">
            Şu anda gerçek kullanım örnekleriyle
            test edilen içerik kaynakları:

            <div class="site-chips">
                <span class="site-chip">
                    YouTube
                </span>

                <span class="site-chip">
                    Wordwall
                </span>

                <span class="site-chip">
                    İlkokul Akademi
                </span>

                <span class="site-chip">
                    İlkokul Evim
                </span>

                <span class="site-chip">
                    ilk-okul.com
                </span>

                <span class="site-chip">
                    TestSaati
                </span>

                <span class="site-chip">
                    Eğitimgen
                </span>
            </div>
        </div>
    </details>

    <form
        class="url-form"
        method="post"
        action="/resolve"
    >
        <label for="url">
            Bağlantı
        </label>

        <input
            id="url"
            name="url"
            type="url"
            inputmode="url"
            autocomplete="off"
            autocapitalize="off"
            spellcheck="false"
            placeholder="https://..."
            required
            autofocus
        >

        <button
            class="url-submit"
            type="submit"
        >
            Göster
        </button>
    </form>

    <details class="suggest-box">
        <summary>
            <strong>Site öner</strong>
        </summary>

        <p>
            Kullandığınız eğitim sitesi henüz
            desteklenmiyorsa bağlantıyı proje
            sayfasından iletebilirsiniz.
        </p>

        <a
            class="text-link"
            href="https://github.com/humit/goster.me/issues/new"
            rel="noopener noreferrer"
            target="_blank"
        >
            Site önerisi gönder ↗
        </a>
    </details>

    <div class="home-footer">
        <span>
            Reklamları değil, dikkat dağıtan
            web ortamını azaltmayı hedefler.
        </span>

        <a
            href="https://github.com/humit/goster.me"
            rel="noopener noreferrer"
            target="_blank"
        >
            Açık kaynak ↗
        </a>
    </div>
</main>

<script>
const supportedToggle =
    document.getElementById(
        "supported-toggle"
    );

const supported =
    document.getElementById(
        "supported"
    );

supportedToggle.addEventListener(
    "click",
    () => {
        supported.open =
            !supported.open;
    }
);
</script>
""",
    )




def render_result(
    item_id: str,
    item: ResolvedContent,
) -> str:
    title = clean_title(item.title)

    return document(
        title,
        f"""
<main>
    <h1>{escape(title)}</h1>

    <div class="card">
        <div class="status-ok">
            ✓ İçerik hazır
        </div>

        <p>
            Kaynak:
            <strong>{escape(hostname(item.source_url))}</strong>
        </p>

        <div class="actions">
            <a
                class="button"
                href="/g/{escape(item_id)}"
            >
                Temiz görünümü aç
            </a>

            <button
                class="secondary"
                id="copy"
                type="button"
            >
                Bağlantıyı kopyala
            </button>

            <button
                class="secondary"
                id="share"
                type="button"
            >
                Paylaş
            </button>
        </div>
    </div>

    <p class="source">
        Kaynak bağlantı:
        {escape(item.source_url)}
    </p>
</main>

<script>
const cleanUrl =
    location.origin + "/g/{escape(item_id)}";

document.getElementById("copy").addEventListener(
    "click",
    async () => {{
        await navigator.clipboard.writeText(cleanUrl);
        document.getElementById("copy").textContent =
            "Kopyalandı ✓";
    }}
);

document.getElementById("share").addEventListener(
    "click",
    async () => {{
        if (navigator.share) {{
            await navigator.share({{
                title: {json.dumps(title)},
                url: cleanUrl
            }});
            return;
        }}

        await navigator.clipboard.writeText(cleanUrl);
        document.getElementById("share").textContent =
            "Bağlantı kopyalandı ✓";
    }}
);
</script>
""",
    )


def preview_actions(
    item_id: str,
    *,
    back_href: str = "/",
) -> str:
    return f"""
<div class="viewer-toolbar">
    <div class="viewer-toolbar-group">
        <a
            class="viewer-icon"
            href="{escape(back_href)}"
            aria-label="Geri dön"
            title="Geri dön"
        >
            ←
        </a>
    </div>

    <div class="viewer-toolbar-group">
        <button
            id="viewer-copy"
            class="viewer-icon"
            type="button"
            aria-label="Bağlantıyı kopyala"
            title="Bağlantıyı kopyala"
        >
            ⧉
        </button>

        <button
            id="viewer-share"
            class="viewer-icon"
            type="button"
            aria-label="Paylaş"
            title="Paylaş"
        >
            ↗
        </button>
    </div>
</div>

<script>
(() => {{
    const cleanUrl =
        location.origin
        + "/g/{escape(item_id)}";

    const copy =
        document.getElementById(
            "viewer-copy"
        );

    const share =
        document.getElementById(
            "viewer-share"
        );

    copy?.addEventListener(
        "click",
        async () => {{
            await navigator.clipboard.writeText(
                cleanUrl
            );

            const old =
                copy.textContent;

            copy.textContent = "✓";

            setTimeout(
                () => {{
                    copy.textContent = old;
                }},
                1200
            );
        }}
    );

    share?.addEventListener(
        "click",
        async () => {{
            if (navigator.share) {{
                try {{
                    await navigator.share({{
                        url: cleanUrl
                    }});

                    return;
                }} catch (_) {{
                }}
            }}

            await navigator.clipboard.writeText(
                cleanUrl
            );

            const old =
                share.textContent;

            share.textContent = "✓";

            setTimeout(
                () => {{
                    share.textContent = old;
                }},
                1200
            );
        }}
    );
}})();
</script>
"""


def render_youtube_embed(
    item_id: str,
    item: ResolvedContent,
) -> str:
    title = clean_title(item.title)

    if not item.content_url:
        raise ValueError(
            "YouTube embed URL is missing."
        )

    body = r"""
<div
    id="youtube-viewer"
    class="fullscreen-viewer youtube-viewer"
>
    __PREVIEW_ACTIONS__

    <div
        id="player-host"
        class="youtube-frame"
    ></div>

    <div
        id="finished"
        class="youtube-finished"
        hidden
    >
        <div class="youtube-finished-card">
            <strong>Video tamamlandı</strong>

            <button
                id="replay"
                type="button"
            >
                Tekrar izle
            </button>

            <a
                class="button secondary"
                href="/"
            >
                Geri dön
            </a>
        </div>
    </div>
</div>

<script>
const viewer =
    document.getElementById(
        "youtube-viewer"
    );

const host =
    document.getElementById(
        "player-host"
    );

const finished =
    document.getElementById(
        "finished"
    );

const embedUrl =
    new URL(__EMBED_URL__);

embedUrl.searchParams.set(
    "origin",
    location.origin
);

embedUrl.searchParams.set(
    "fs",
    "0"
);

embedUrl.searchParams.set(
    "autoplay",
    "0"
);

embedUrl.searchParams.set(
    "playsinline",
    "1"
);

embedUrl.searchParams.set(
    "rel",
    "0"
);

embedUrl.searchParams.set(
    "iv_load_policy",
    "3"
);

embedUrl.searchParams.set(
    "hl",
    "tr"
);

embedUrl.searchParams.set(
    "enablejsapi",
    "1"
);


/*
 * Create the iframe ourselves so containment
 * attributes are present before YouTube loads.
 */
const iframe =
    document.createElement(
        "iframe"
    );

iframe.id =
    "yt-player";

iframe.className =
    "youtube-player-frame";

iframe.title =
    __TITLE__;

iframe.setAttribute(
    "sandbox",
    [
        "allow-scripts",
        "allow-same-origin",
        "allow-presentation"
    ].join(" ")
);

iframe.setAttribute(
    "allow",
    [
        "autoplay",
        "encrypted-media",
        "picture-in-picture",
        "fullscreen"
    ].join("; ")
);

iframe.setAttribute(
    "referrerpolicy",
    "strict-origin-when-cross-origin"
);

iframe.setAttribute(
    "allowfullscreen",
    ""
);

/*
 * Set src only after sandbox and permissions.
 */
iframe.src =
    embedUrl.toString();

host.appendChild(
    iframe
);


/*
 * Load IFrame API after the contained iframe exists.
 */
const tag =
    document.createElement(
        "script"
    );

tag.src =
    "https://www.youtube.com/iframe_api";

document.head.appendChild(
    tag
);

let player = null;

window.onYouTubeIframeAPIReady =
    () => {
        player =
            new YT.Player(
                iframe,
                {
                    events: {
                        onStateChange:
                            event => {
                                if (
                                    event.data ===
                                    YT.PlayerState.ENDED
                                ) {
                                    finished.hidden =
                                        false;
                                }
                            }
                    }
                }
            );
    };


document.getElementById(
    "replay"
).addEventListener(
    "click",
    () => {
        finished.hidden =
            true;

        if (player) {
            player.seekTo(
                0,
                true
            );

            player.playVideo();
        }
    }
);
</script>
"""

    body = body.replace(
        "__PREVIEW_ACTIONS__",
        preview_actions(
            item_id,
        ),
    )

    body = body.replace(
        "__EMBED_URL__",
        json.dumps(item.content_url),
    )

    body = body.replace(
        "__TITLE__",
        json.dumps(title),
    )

    return document(
        title,
        body,
    )


def render_embed(
    item_id: str,
    item: ResolvedContent,
    content_url: str,
    title: str,
) -> str:
    return document(
        title,
        f"""
<div class="fullscreen-viewer">
    {preview_actions(
        item_id,
        back_href=(
            f"/g/{escape(item_id)}"
            if item.render_mode == "embed-collection"
            else "/"
        ),
    )}

    <iframe
        class="fullscreen-frame"
        src="{escape(content_url)}"
        title="{escape(title)}"
        allowfullscreen
    ></iframe>
</div>
""",
    )


def render_collection(
    item_id: str,
    item: ResolvedContent,
) -> str:
    title = clean_title(item.title)

    cards = []

    for index, _ in enumerate(
        item.content_urls,
        start=1,
    ):
        cards.append(
            f"""
<a
    class="activity"
    href="/g/{escape(item_id)}/e/{index}"
>
    <span>
        <strong>Etkinlik {index}</strong>
        <small>Etkinliği aç</small>
    </span>

    <span class="arrow">›</span>
</a>
"""
        )

    return document(
        title,
        f"""
<main>
    <div class="collection-head">
        <div>
            <h1>{escape(title)}</h1>

            <p class="subtitle">
                {len(item.content_urls)} etkinlik
            </p>
        </div>

        <div class="collection-actions">
            <button
                id="viewer-copy"
                class="viewer-icon"
                type="button"
                aria-label="Bağlantıyı kopyala"
                title="Bağlantıyı kopyala"
            >
                ⧉
            </button>

            <button
                id="viewer-share"
                class="viewer-icon"
                type="button"
                aria-label="Paylaş"
                title="Paylaş"
            >
                ↗
            </button>
        </div>
    </div>

    <div class="activity-list">
        {''.join(cards)}
    </div>

    {preview_actions(item_id).replace(
        '<div class="viewer-toolbar">',
        '<div class="viewer-toolbar" hidden>',
    )}
</main>
""",
    )


def isolate_css(selector: str) -> str:
    selector_json = json.dumps(selector)

    return f"""
<style id="goster-isolation">
html,
body {{
    background: #ffffff !important;
}}

body * {{
    visibility: hidden !important;
}}

/*
 * Advertising and tracking elements should not merely be invisible:
 * remove their layout footprint as well.
 */
.adsbygoogle,
.google-auto-placed,
ins.adsbygoogle,
iframe[id^="google_ads"],
iframe[src*="googlesyndication"],
iframe[src*="doubleclick"] {{
    display: none !important;
    width: 0 !important;
    height: 0 !important;
    min-width: 0 !important;
    min-height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}}

{selector},
{selector} * {{
    visibility: visible !important;
}}

{selector} {{
    position: absolute !important;
    top: 0 !important;
    left: 0 !important;
    width: 100% !important;
    max-width: none !important;
    margin: 0 !important;
    z-index: 2147483647 !important;
}}
</style>

<script>
(() => {{
    const allowed = {selector_json};

    document.addEventListener(
        "click",
        event => {{
            const link = event.target.closest("a");

            if (!link) {{
                return;
            }}

            const href = link.getAttribute("href");

            if (!href) {{
                return;
            }}

            if (
                href.startsWith("#")
                || href.startsWith("javascript:")
            ) {{
                return;
            }}

            event.preventDefault();
        }},
        true
    );

    window.open = () => null;
}})();
</script>
"""


def render_isolated_source(
    item: ResolvedContent,
) -> str:
    if not item.content_url or not item.selector:
        raise ValueError(
            "Isolated content is missing URL or selector."
        )

    source_host = hostname(item.content_url)

    final_url, source_html = fetch_html(
        item.content_url,
        allowed_hosts={
            source_host,
            "www." + source_host
            if not source_host.startswith("www.")
            else source_host.removeprefix("www."),
        },
    )

    injection = isolate_css(
        item.selector
    )

    #
    # Flying Words has a deliberately spacious source layout.
    # In the clean child view that pushes the initial action
    # below the first viewport. Compact only this known family;
    # keep the reading screen itself untouched.
    #
    if (
        item.adapter == "ilk-okul-native"
        and item.selector == "#container"
    ):
        injection += """
<style id="goster-flying-words">
#container {
    min-height: 0 !important;
    height: auto !important;
    padding-top: 16px !important;
    padding-bottom: 24px !important;
}

#speed-selector {
    margin-top: 12px !important;
    margin-bottom: 12px !important;
}

#reading-speed {
    margin-top: 8px !important;
    margin-bottom: 8px !important;
}

#reading-screen {
    margin-top: 12px !important;
}

/*
 * Source pages in this family may contain large spacer/ad slots
 * between the instructions and the start controls.
 */
#container > ins,
#container > .adsbygoogle,
#container > [class*="advert"],
#container > [class*="reklam"],
#container > [id*="advert"],
#container > [id*="reklam"] {
    display: none !important;
}

/*
 * Prevent empty direct children from consuming a large block
 * on the initial screen.
 */
#container > div:empty {
    min-height: 0 !important;
    height: 0 !important;
    margin: 0 !important;
    padding: 0 !important;
}
</style>
"""

    #
    # The source document is now served from /v/<id>.
    # Preserve the original document base so relative CSS,
    # JavaScript, images, fonts and audio continue to load
    # from the source site.
    #
    base_tag = (
        '<base href="'
        + escape(final_url)
        + '">'
    )

    lower = source_html.lower()
    head_start = lower.find("<head")

    if head_start >= 0:
        head_open_end = source_html.find(
            ">",
            head_start,
        )

        if head_open_end >= 0:
            source_html = (
                source_html[:head_open_end + 1]
                + base_tag
                + source_html[head_open_end + 1:]
            )
        else:
            source_html = base_tag + source_html
    else:
        source_html = base_tag + source_html

    lower = source_html.lower()
    head_pos = lower.find("</head>")

    if head_pos >= 0:
        source_html = (
            source_html[:head_pos]
            + injection
            + source_html[head_pos:]
        )
    else:
        source_html = injection + source_html

    return source_html


def render_child(
    item_id: str,
    item: ResolvedContent,
) -> str:
    title = clean_title(item.title)

    if item.render_mode == "youtube-embed":
        return render_youtube_embed(
            item_id,
            item,
        )

    if item.render_mode == "embed-collection":
        return render_collection(
            item_id,
            item,
        )

    if item.render_mode == "embed":
        if not item.content_url:
            raise ValueError("Missing embed URL.")

        return render_embed(
            item_id,
            item,
            item.content_url,
            title,
        )

    if item.render_mode == "isolate":
        return document(
            title,
            f"""
<div class="fullscreen-viewer">
    {preview_actions(item_id)}

    <iframe
        class="fullscreen-frame"
        src="/v/{escape(item_id)}"
        title="{escape(title)}"
        allowfullscreen
    ></iframe>
</div>
""",
        )

    return document(
        title,
        f"""
<main>
    <h1>{escape(title)}</h1>

    <div class="card">
        <div class="status-error">
            Bu içerik için henüz temiz görünüm hazırlanmadı.
        </div>
    </div>
</main>
""",
    )


class Handler(BaseHTTPRequestHandler):
    server_version = "GosterLocal/0.1"

    def send_html(
        self,
        status: int,
        value: str,
    ) -> None:
        body = value.encode("utf-8")

        self.send_response(status)
        self.send_header(
            "Content-Type",
            "text/html; charset=utf-8",
        )
        self.send_header(
            "Content-Length",
            str(len(body)),
        )
        self.send_header(
            "Cache-Control",
            "no-store",
        )
        self.end_headers()
        self.wfile.write(body)

    def redirect(
        self,
        location: str,
    ) -> None:
        self.send_response(303)
        self.send_header(
            "Location",
            location,
        )
        self.end_headers()

    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/":
            self.send_html(
                200,
                render_home(),
            )
            return

        parts = [
            part
            for part in path.split("/")
            if part
        ]

        if len(parts) == 2 and parts[0] == "g":
            item = get_item(parts[1])

            if item is None:
                self.send_error(404)
                return

            self.send_html(
                200,
                render_child(
                    parts[1],
                    item,
                ),
            )
            return

        if (
            len(parts) == 4
            and parts[0] == "g"
            and parts[2] == "e"
        ):
            item = get_item(parts[1])

            if item is None:
                self.send_error(404)
                return

            try:
                index = int(parts[3]) - 1
                content_url = item.content_urls[index]
            except (
                ValueError,
                IndexError,
            ):
                self.send_error(404)
                return

            self.send_html(
                200,
                render_embed(
                    parts[1],
                    item,
                    content_url,
                    f"Etkinlik {index + 1}",
                ),
            )
            return

        if len(parts) == 2 and parts[0] == "v":
            item = get_item(parts[1])

            if item is None:
                self.send_error(404)
                return

            if item.render_mode != "isolate":
                self.send_error(404)
                return

            try:
                value = render_isolated_source(
                    item
                )
            except Exception as exc:
                self.send_html(
                    502,
                    document(
                        "İçerik açılamadı",
                        f"""
<main>
    <h1>İçerik açılamadı</h1>
    <div class="card">
        <div class="status-error">
            {escape(str(exc))}
        </div>
    </div>
</main>
""",
                    ),
                )
                return

            self.send_html(
                200,
                value,
            )
            return

        self.send_error(404)

    def do_POST(self):
        parsed = urlparse(self.path)

        if parsed.path != "/resolve":
            self.send_error(404)
            return

        try:
            length = int(
                self.headers.get(
                    "Content-Length",
                    "0",
                )
            )

            if length <= 0 or length > 16384:
                raise ValueError(
                    "Invalid request size."
                )

            data = parse_qs(
                self.rfile.read(length).decode(
                    "utf-8"
                )
            )

            url = (
                data.get(
                    "url",
                    [""],
                )[0]
                .strip()
            )

            if not url:
                raise ValueError(
                    "Bağlantı boş olamaz."
                )

            item = resolve_url(url)
            item_id = save_item(item)

        except AdapterError as exc:
            self.send_html(
                400,
                document(
                    "Bağlantı desteklenmiyor",
                    f"""
<main>
    <h1>Bu bağlantıyı hazırlayamadım</h1>

    <div class="card">
        <div class="status-error">
            {escape(str(exc))}
        </div>
    </div>

    <div class="actions">
        <a class="button secondary" href="/">
            Geri dön
        </a>
    </div>
</main>
""",
                ),
            )
            return

        except Exception as exc:
            self.send_html(
                400,
                document(
                    "Hata",
                    f"""
<main>
    <h1>Bir sorun oluştu</h1>

    <div class="card">
        <div class="status-error">
            {escape(str(exc))}
        </div>
    </div>
</main>
""",
                ),
            )
            return

        self.redirect(
            f"/g/{item_id}"
        )

    def log_message(self, fmt, *args):
        print(
            f"{self.client_address[0]} "
            f"{self.log_date_time_string()} "
            f"{fmt % args}",
            flush=True,
        )


if __name__ == "__main__":
    print(
        f"Goster local preview listening on "
        f"http://{HOST}:{PORT}",
        flush=True,
    )

    ThreadingHTTPServer(
        (HOST, PORT),
        Handler,
    ).serve_forever()
