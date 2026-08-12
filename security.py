#!/usr/bin/env python3

from __future__ import annotations

import contextvars
import ipaddress
import os
import re
from urllib.error import HTTPError
from urllib.parse import urljoin, urlparse
from urllib.request import HTTPRedirectHandler, build_opener


MAX_URL_LENGTH = int(os.environ.get("GOSTER_MAX_URL_LENGTH", "2048"))
ALLOWED_URL_SCHEMES = {"http", "https"}
ALLOWED_URL_PORTS = {80, 443}
YOUTUBE_VIDEO_ID_RE = re.compile(r"^[A-Za-z0-9_-]{11}$")

_redirect_allowed_hosts: contextvars.ContextVar[frozenset[str]] = (
    contextvars.ContextVar(
        "goster_redirect_allowed_hosts",
        default=frozenset(),
    )
)


class SecurityValidationError(ValueError):
    pass


def validate_public_url(value: str) -> str:
    if not isinstance(value, str):
        raise SecurityValidationError("URL must be text.")

    if len(value) > MAX_URL_LENGTH:
        raise SecurityValidationError("URL is too long.")

    if any(ord(ch) < 32 or ord(ch) == 127 for ch in value):
        raise SecurityValidationError("URL contains control characters.")

    url = value.strip()
    parsed = urlparse(url)

    if parsed.scheme.lower() not in ALLOWED_URL_SCHEMES:
        raise SecurityValidationError("Only HTTP/HTTPS URLs are supported.")

    if not parsed.hostname:
        raise SecurityValidationError("URL has no hostname.")

    if parsed.username is not None or parsed.password is not None:
        raise SecurityValidationError("Credentials in URLs are not allowed.")

    try:
        port = parsed.port
    except ValueError as exc:
        raise SecurityValidationError("URL has an invalid port.") from exc

    if port is not None and port not in ALLOWED_URL_PORTS:
        raise SecurityValidationError("URL port is not allowed.")

    host = parsed.hostname.lower().rstrip(".")

    try:
        ipaddress.ip_address(host)
    except ValueError:
        pass
    else:
        raise SecurityValidationError("IP-address URLs are not allowed.")

    return url


def validate_public_origin(value: str) -> str:
    origin = validate_public_url(value)
    parsed = urlparse(origin)

    if parsed.path not in {"", "/"}:
        raise SecurityValidationError("Public origin must not contain a path.")

    if parsed.query or parsed.fragment:
        raise SecurityValidationError("Public origin must not contain query or fragment.")

    return origin.rstrip("/")


def public_origin() -> str:
    return validate_public_origin(
        os.environ.get("GOSTER_PUBLIC_ORIGIN", "https://goster.me")
    )


def validated_youtube_video_id(value: str | None) -> str | None:
    if value is None:
        return None

    if not YOUTUBE_VIDEO_ID_RE.fullmatch(value):
        return None

    return value


class AllowlistRedirectHandler(HTTPRedirectHandler):
    """Validate every redirect target before urllib opens it."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        absolute = urljoin(req.full_url, newurl)

        try:
            validated = validate_public_url(absolute)
        except SecurityValidationError as exc:
            raise HTTPError(
                absolute,
                code,
                "Blocked unsafe redirect target",
                headers,
                fp,
            ) from exc

        allowed_hosts = _redirect_allowed_hosts.get()
        host = (urlparse(validated).hostname or "").lower().rstrip(".")

        if host not in allowed_hosts:
            raise HTTPError(
                absolute,
                code,
                "Blocked redirect to disallowed host",
                headers,
                fp,
            )

        return super().redirect_request(
            req,
            fp,
            code,
            msg,
            headers,
            validated,
        )


def safe_urlopen(request, *args, **kwargs):
    opener = build_opener(AllowlistRedirectHandler())
    return opener.open(request, *args, **kwargs)


def call_with_redirect_allowlist(
    original_fetch_html,
    url: str,
    allowed_hosts: set[str],
):
    normalized_hosts = frozenset(
        host.lower().rstrip(".")
        for host in allowed_hosts
    )

    token = _redirect_allowed_hosts.set(normalized_hosts)

    try:
        return original_fetch_html(url, allowed_hosts)
    finally:
        _redirect_allowed_hosts.reset(token)
