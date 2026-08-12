#!/usr/bin/env python3

from __future__ import annotations

import html
import os

from http.server import ThreadingHTTPServer
from urllib.parse import urlparse

import product_app as app
import adapter_extensions  # noqa: F401

from sandbox_auth import signed_query, signing_key
from security import validate_public_origin


SANDBOX_ORIGIN = validate_public_origin(
    os.environ.get(
        "GOSTER_SANDBOX_ORIGIN",
        "https://s.goster.me",
    )
)


def resolve_with_sandbox(url: str):
    """Use the P0-hardened adapter stack while allowing isolate results.

    product_app installed URL, redirect, and adapter hardening at import time.
    Its captured original resolver therefore runs against those hardened module
    globals, but does not apply the temporary isolate fail-closed policy.
    """
    return app._ORIGINAL_RESOLVE_URL(url)


# Handler.do_POST resolves this global at request time.
app.hardened_resolve_url = resolve_with_sandbox


def compact_preview_actions(
    item_id: str,
    *,
    back_href: str = "/",
) -> str:
    """Render compact branded viewer controls without linking to the source site."""
    del back_href
    canonical = f"/{app.escape(item_id)}"
    item = app.STORE.get(item_id, touch=False)
    source_url = item.source_url if item is not None else ""
    source_host = urlparse(source_url).hostname or "kaynak"

    return f"""
<style>
.viewer-compact-menu {{
    position: fixed;
    right: max(.7rem, env(safe-area-inset-right));
    bottom: max(4.75rem, calc(env(safe-area-inset-bottom) + 3.75rem));
    z-index: 2147483646;
    font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.viewer-compact-menu[open]::before {{
    content: "";
    position: fixed;
    inset: 0;
    z-index: 0;
    background: transparent;
}}
.viewer-compact-menu > summary {{
    position: relative;
    z-index: 2;
    width: 4.5rem;
    min-height: 3rem;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    gap: .08rem;
    padding: .35rem .45rem .28rem;
    box-sizing: border-box;
    list-style: none;
    cursor: pointer;
    border: 1px solid rgba(255,255,255,.2);
    border-radius: .85rem;
    background: rgba(9,11,14,.74);
    color: #fff;
    opacity: .84;
    backdrop-filter: blur(10px);
    -webkit-backdrop-filter: blur(10px);
    user-select: none;
    box-shadow: 0 .3rem 1rem rgba(0,0,0,.14);
}}
.viewer-compact-menu > summary::-webkit-details-marker {{ display: none; }}
.viewer-compact-menu > summary:hover,
.viewer-compact-menu > summary:focus-visible,
.viewer-compact-menu[open] > summary {{ opacity: 1; }}
.viewer-compact-brand {{
    font-size: .67rem;
    font-weight: 700;
    letter-spacing: -.02em;
    line-height: 1.05;
}}
.viewer-compact-dots {{
    font-size: 1rem;
    font-weight: 700;
    letter-spacing: .09em;
    line-height: .8;
}}
.viewer-compact-panel {{
    position: absolute;
    z-index: 2;
    right: 0;
    bottom: calc(100% + .5rem);
    width: min(19rem, calc(100vw - 1.4rem));
    padding: .45rem;
    border: 1px solid rgba(255,255,255,.13);
    border-radius: .85rem;
    background: rgba(12,14,18,.95);
    color: #fff;
    box-shadow: 0 .6rem 1.8rem rgba(0,0,0,.22);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
}}
.viewer-compact-grid {{
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: .35rem;
    align-items: stretch;
}}
.viewer-compact-action,
.viewer-source-summary {{
    min-height: 2.25rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
    box-sizing: border-box;
    padding: 0 .7rem;
    border: 0;
    border-radius: .6rem;
    background: rgba(255,255,255,.08);
    color: #fff;
    font: inherit;
    font-size: .76rem;
    text-decoration: none;
    cursor: pointer;
}}
.viewer-source {{
    min-width: 0;
    margin: 0;
}}
.viewer-source[open] {{ grid-column: 1 / -1; }}
.viewer-source-summary {{
    width: 100%;
    justify-content: center;
    list-style: none;
    color: rgba(255,255,255,.76);
}}
.viewer-source-summary::-webkit-details-marker {{ display: none; }}
.viewer-source-body {{
    padding: .5rem .2rem .1rem;
}}
.viewer-source-url {{
    max-height: 5rem;
    overflow: auto;
    margin-bottom: .45rem;
    color: rgba(255,255,255,.72);
    font: 500 .68rem/1.35 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    overflow-wrap: anywhere;
}}
@media (max-width: 430px) {{
    .viewer-compact-menu {{
        right: max(.55rem, env(safe-area-inset-right));
        bottom: max(5rem, calc(env(safe-area-inset-bottom) + 4rem));
    }}
    .viewer-compact-menu > summary {{ width: 4.25rem; min-height: 2.85rem; }}
}}
</style>
<details class="viewer-compact-menu">
    <summary aria-label="goster.me menüsü" title="goster.me menüsü">
        <span class="viewer-compact-brand">goster.me</span>
        <span class="viewer-compact-dots" aria-hidden="true">•••</span>
    </summary>
    <div class="viewer-compact-panel">
        <div class="viewer-compact-grid">
            <button class="viewer-compact-action" type="button" data-action="share" data-url="{canonical}">Paylaş</button>
            <a class="viewer-compact-action" href="/q/{app.escape(item_id)}" data-action="qr">QR</a>
            <a class="viewer-compact-action" href="/">Ana Sayfa</a>
            <details class="viewer-source">
                <summary class="viewer-source-summary">Kaynak</summary>
                <div class="viewer-source-body">
                    <div class="viewer-source-label">Kaynak: {app.escape(source_host)}</div>
                    <div class="viewer-source-url">{app.escape(source_url)}</div>
                    <button
                        class="viewer-compact-action"
                        type="button"
                        data-action="copy"
                        data-url="{app.escape(source_url)}"
                    >URL'yi kopyala</button>
                </div>
            </details>
        </div>
    </div>
</details>
"""


# Keep all viewer types on the same compact control surface. The source is
# informational only: no direct navigation back to the third-party page.
app.branded_preview_actions = compact_preview_actions
app.legacy.preview_actions = compact_preview_actions


def render_sandbox_shell(code: str, item) -> str:
    title = app.legacy.clean_title(item.title)
    query = signed_query(code)
    sandbox_url = html.escape(
        f"{SANDBOX_ORIGIN}/v/{code}?{query}",
        quote=True,
    )

    return app.product_document(
        title,
        f"""
<div class="fullscreen-viewer">
    {app.branded_preview_actions(code)}

    <iframe
        class="fullscreen-frame"
        src="{sandbox_url}"
        title="{app.escape(title)}"
        sandbox="allow-scripts allow-same-origin allow-modals allow-pointer-lock allow-presentation"
        referrerpolicy="no-referrer"
        allow="fullscreen"
        allowfullscreen
    ></iframe>
</div>
""",
    )


class Handler(app.Handler):
    server_version = "goster.me"
    sys_version = ""

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        parts = [part for part in path.split("/") if part]

        if not parsed.query and len(parts) == 1:
            code = parts[0].lower()

            if app.SHORT_CODE_RE.fullmatch(code):
                item = app.STORE.get(code, touch=False)

                if item is not None and item.render_mode == "isolate":
                    # Count only content that is actually served by the shell.
                    item = app.STORE.get(code)
                    app.ANALYTICS.record(
                        "viewer_open",
                        provider=item.provider,
                        adapter=item.adapter,
                        render_mode=item.render_mode,
                        )
                    self.send_html(200, render_sandbox_shell(code, item))
                    return

        super().do_GET()


if __name__ == "__main__":
    # Fail closed before accepting traffic if deployment forgot the shared
    # sandbox capability secret.
    signing_key()
    purged = app.STORE.purge_expired()

    print(
        f"goster.me listening on http://{app.HOST}:{app.PORT} "
        f"(public_origin={app.PUBLIC_ORIGIN}, sandbox_origin={SANDBOX_ORIGIN}, "
        f"short={app.SHORT_CODE_LENGTH}, ttl={app.ttl_days():g}d, purged={purged})",
        flush=True,
    )

    ThreadingHTTPServer((app.HOST, app.PORT), Handler).serve_forever()
