#!/usr/bin/env python3

from __future__ import annotations

import html
import json
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


HOST = "0.0.0.0"
PORT = 8090

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
        system-ui,
        -apple-system,
        BlinkMacSystemFont,
        "Segoe UI",
        sans-serif;
    color-scheme: dark;
}

* {
    box-sizing: border-box;
}

html,
body {
    margin: 0;
    min-height: 100%;
    background: #111827;
    color: #f9fafb;
}

body {
    min-height: 100vh;
}

main {
    width: min(100%, 760px);
    margin: 0 auto;
    padding:
        max(22px, env(safe-area-inset-top))
        18px
        max(36px, env(safe-area-inset-bottom));
}

h1 {
    margin: 8px 0 8px;
    font-size: clamp(26px, 5vw, 36px);
    line-height: 1.15;
}

.subtitle {
    margin: 0 0 28px;
    color: #9ca3af;
    line-height: 1.5;
}

label {
    display: block;
    margin: 22px 0 8px;
    font-weight: 700;
}

input,
button,
.button {
    font: inherit;
}

input {
    width: 100%;
    min-height: 56px;
    border: 1px solid #4b5563;
    border-radius: 14px;
    padding: 0 14px;
    background: #1f2937;
    color: #fff;
    font-size: 16px;
}

button,
.button {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-height: 52px;
    border: 0;
    border-radius: 14px;
    padding: 0 18px;
    background: #22c55e;
    color: #052e16;
    font-weight: 800;
    text-decoration: none;
    cursor: pointer;
}

.primary {
    width: 100%;
    margin-top: 18px;
}

.secondary {
    background: #1f2937;
    color: #f9fafb;
    border: 1px solid #4b5563;
}

.card {
    margin-top: 18px;
    padding: 18px;
    border: 1px solid #374151;
    border-radius: 18px;
    background: #1f2937;
}

.actions {
    display: grid;
    gap: 10px;
    margin-top: 18px;
}

.status-ok {
    color: #86efac;
    font-weight: 700;
}

.status-error {
    color: #fca5a5;
    font-weight: 700;
}

.activity-list {
    display: grid;
    gap: 12px;
    margin-top: 22px;
}

.activity {
    width: 100%;
    min-height: 82px;
    margin: 0;
    background: #1f2937;
    color: #f9fafb;
    border: 1px solid #374151;
    border-radius: 18px;
    padding: 16px 18px;
    text-align: left;
    display: flex;
    align-items: center;
    justify-content: space-between;
}

.activity strong {
    display: block;
    font-size: 18px;
}

.activity small {
    display: block;
    margin-top: 5px;
    color: #9ca3af;
}

.arrow {
    color: #60a5fa;
    font-size: 34px;
}

.topbar {
    display: flex;
    align-items: center;
    gap: 12px;
    margin-bottom: 18px;
}

.topbar a {
    color: #d1d5db;
    text-decoration: none;
    font-weight: 700;
}

.frame-wrap {
    margin-top: 18px;
    overflow: hidden;
    border-radius: 16px;
    background: white;
}

iframe {
    display: block;
    width: 100%;
    min-height: 680px;
    height: 82vh;
    border: 0;
    background: white;
}

.source {
    margin-top: 20px;
    color: #6b7280;
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

.viewer-fullscreen {
    position: fixed;
    z-index: 2147483647;
    top: max(
        10px,
        env(safe-area-inset-top)
    );
    right: max(
        10px,
        env(safe-area-inset-right)
    );

    width: 46px;
    height: 46px;
    min-height: 46px;
    margin: 0;
    padding: 0;

    border-radius: 50%;
    background:
        rgba(17, 24, 39, 0.88);
    color: #fff;

    font-size: 25px;
    line-height: 1;
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

.viewer-back {
    position: fixed;
    z-index: 2147483647;
    top: max(10px, env(safe-area-inset-top));
    left: max(10px, env(safe-area-inset-left));
    width: 44px;
    height: 44px;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: rgba(17, 24, 39, 0.88);
    color: #fff;
    text-decoration: none;
    font-size: 24px;
    font-weight: 800;
    box-shadow: 0 2px 10px rgba(0, 0, 0, 0.30);
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
<main>
    <h1>Göster</h1>

    <p class="subtitle">
        Öğretmenin gönderdiği bağlantıyı yapıştırın.
        İçeriği mümkün olduğunca sade bir görünümde hazırlayalım.
    </p>

    <form method="post" action="/resolve">
        <label for="url">Bağlantı</label>

        <input
            id="url"
            name="url"
            type="url"
            inputmode="url"
            autocomplete="off"
            autocapitalize="off"
            placeholder="https://..."
            required
        >

        <button class="primary" type="submit">
            Hazırla
        </button>
    </form>
</main>
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
    <a
        class="viewer-back"
        href="/"
        aria-label="Geri dön"
    >
        ←
    </a>

    <button
        id="viewer-fullscreen"
        class="viewer-fullscreen"
        type="button"
        aria-label="Tam ekran"
    >
        ⛶
    </button>

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

const fullscreenButton =
    document.getElementById(
        "viewer-fullscreen"
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


async function enterFullscreen() {
    try {
        if (!document.fullscreenElement) {
            await viewer.requestFullscreen();
        }

        if (
            screen.orientation
            && screen.orientation.lock
        ) {
            try {
                await screen.orientation.lock(
                    "landscape"
                );
            } catch (_) {
            }
        }
    } catch (_) {
    }
}


function unlockOrientation() {
    if (
        screen.orientation
        && screen.orientation.unlock
    ) {
        try {
            screen.orientation.unlock();
        } catch (_) {
        }
    }
}


fullscreenButton.addEventListener(
    "click",
    enterFullscreen
);


document.addEventListener(
    "fullscreenchange",
    () => {
        if (!document.fullscreenElement) {
            unlockOrientation();
        }
    }
);


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
    <a
        class="viewer-back"
        href="/g/{escape(item_id)}"
        aria-label="Etkinliklere dön"
    >
        ←
    </a>

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
    <h1>{escape(title)}</h1>

    <p class="subtitle">
        {len(item.content_urls)} etkinlik
    </p>

    <div class="activity-list">
        {''.join(cards)}
    </div>
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
    <a
        class="viewer-back"
        href="/"
        aria-label="Geri dön"
    >
        ←
    </a>

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

        self.send_html(
            200,
            render_result(
                item_id,
                item,
            ),
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
