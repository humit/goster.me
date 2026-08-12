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
    """Render low-profile viewer controls without linking to the source site."""
    canonical = f"/{app.escape(item_id)}"
    item = app.STORE.get(item_id, touch=False)
    source_url = item.source_url if item is not None else ""
    source_host = urlparse(source_url).hostname or "kaynak"

    return f"""
<style>
.viewer-compact-menu {{
    position: fixed;
    right: max(.45rem, env(safe-area-inset-right));
    top: 48%;
    transform: translateY(-50%);
    z-index: 2147483646;
    font-family: ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
}}
.viewer-compact-menu > summary {{
    width: 2.35rem;
    height: 2.35rem;
    display: grid;
    place-items: center;
    list-style: none;
    cursor: pointer;
    border: 1px solid rgba(255,255,255,.16);
    border-radius: 999px;
    background: rgba(9,11,14,.42);
    color: #fff;
    opacity: .42;
    backdrop-filter: blur(8px);
    -webkit-backdrop-filter: blur(8px);
    font-size: 1.05rem;
    line-height: 1;
    user-select: none;
}}
.viewer-compact-menu > summary::-webkit-details-marker {{ display: none; }}
.viewer-compact-menu > summary:hover,
.viewer-compact-menu > summary:focus-visible,
.viewer-compact-menu[open] > summary {{ opacity: .95; }}
.viewer-compact-panel {{
    position: absolute;
    right: 0;
    top: calc(100% + .45rem);
    width: min(19rem, calc(100vw - 1.4rem));
    padding: .45rem;
    border: 1px solid rgba(255,255,255,.13);
    border-radius: .85rem;
    background: rgba(12,14,18,.94);
    color: #fff;
    box-shadow: 0 .6rem 1.8rem rgba(0,0,0,.22);
    backdrop-filter: blur(14px);
    -webkit-backdrop-filter: blur(14px);
}}
.viewer-compact-row {{
    display: flex;
    gap: .35rem;
    align-items: center;
    flex-wrap: wrap;
}}
.viewer-compact-action,
.viewer-source-summary {{
    min-height: 2.25rem;
    display: inline-flex;
    align-items: center;
    justify-content: center;
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
.viewer-source {{ margin-top: .4rem; }}
.viewer-source-summary {{
    width: 100%;
    box-sizing: border-box;
    justify-content: flex-start;
    list-style: none;
    color: rgba(255,255,255,.76);
}}
.viewer-source-summary::-webkit-details-marker {{ display: none; }}
.viewer-source-body {{ padding: .5rem .2rem .1rem; }}
.viewer-source-url {{
    max-height: 5rem;
    overflow: auto;
    margin-bottom: .45rem;
    color: rgba(255,255,255,.72);
    font: 500 .68rem/1.35 ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
    overflow-wrap: anywhere;
}}
@media (max-width: 430px) {{
    .viewer-compact-menu {{ right: max(.35rem, env(safe-area-inset-right)); top: 56%; }}
}}
</style>
<details class="viewer-compact-menu">
    <summary aria-label="goster.me menüsü" title="goster.me menüsü">•••</summary>
    <div class="viewer-compact-panel">
        <div class="viewer-compact-row">
            <a class="viewer-compact-action" href="{app.escape(back_href)}">← Geri</a>
            <button class="viewer-compact-action" type="button" data-action="copy" data-url="{canonical}">Kopyala</button>
            <button class="viewer-compact-action" type="button" data-action="share" data-url="{canonical}">Paylaş</button>
            <a class="viewer-compact-action" href="/q/{app.escape(item_id)}" data-action="qr">QR</a>
        </div>
        <details class="viewer-source">
            <summary class="viewer-source-summary">Kaynak: {app.escape(source_host)}</summary>
            <div class="viewer-source-body">
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
