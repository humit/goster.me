#!/usr/bin/env python3

from __future__ import annotations

import html
import os

from http.server import ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

import product_app as app

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
            <a class="viewer-compact-action" href="/contact?from={app.escape(item_id)}">İletişim</a>
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


def viewer_document(title: str, body: str, **kwargs) -> str:
    """Load viewer-only controls without adding their CSS to stable pages."""
    return app.product_document(
        title,
        body,
        viewer_controls=True,
        **kwargs,
    )


app.legacy.document = viewer_document


def contact_return_code(query: str) -> str | None:
    """Accept only a live local short code as a contact-page return target."""
    values = parse_qs(query, keep_blank_values=True)
    if set(values) != {"from"} or len(values["from"]) != 1:
        return None

    code = values["from"][0].strip().lower()
    if not app.SHORT_CODE_RE.fullmatch(code):
        return None
    if app.STORE.get(code, touch=False) is None:
        return None
    return code


def render_contact_from_viewer(code: str) -> str:
    """Render the native contact page with a safe local return target."""
    page = app.render_contact()
    default_back = '<a class="text-link" href="/">← Geri</a>'
    viewer_back = f'<a class="text-link" href="/{app.escape(code)}">← Geri</a>'
    return page.replace(default_back, viewer_back, 1)


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
        viewer_controls=True,
    )


class Handler(app.Handler):
    server_version = "goster.me"
    sys_version = ""

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        path = parsed.path
        parts = [part for part in path.split("/") if part]

        if path == "/contact" and parsed.query:
            code = contact_return_code(parsed.query)
            if code is None:
                self.send_error(404)
                return
            if not self.is_head_request():
                app.ANALYTICS.record(
                    "contact_view",
                    visitor_ip=app.client_ip(self),
                )
            self.send_html(200, render_contact_from_viewer(code))
            return

        if not parsed.query and len(parts) == 1:
            code = parts[0].lower()

            if app.SHORT_CODE_RE.fullmatch(code):
                item = app.STORE.get(code, touch=False)

                if item is not None and item.render_mode == "isolate":
                    if not self.is_head_request():
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
