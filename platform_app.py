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
        sandbox="allow-scripts allow-modals allow-pointer-lock allow-presentation"
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
