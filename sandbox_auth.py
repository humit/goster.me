#!/usr/bin/env python3

from __future__ import annotations

import hashlib
import hmac
import os
import time

from urllib.parse import urlencode


DEFAULT_TOKEN_TTL_SECONDS = 10 * 60
MIN_SIGNING_KEY_BYTES = 32


def signing_key() -> bytes:
    value = os.environ.get("GOSTER_SANDBOX_SIGNING_KEY", "").encode("utf-8")

    if len(value) < MIN_SIGNING_KEY_BYTES:
        raise RuntimeError(
            "GOSTER_SANDBOX_SIGNING_KEY must contain at least 32 bytes."
        )

    return value


def _message(code: str, expires_at: int) -> bytes:
    return f"{code}\n{expires_at}".encode("utf-8")


def sign(code: str, expires_at: int) -> str:
    return hmac.new(
        signing_key(),
        _message(code, expires_at),
        hashlib.sha256,
    ).hexdigest()


def signed_query(
    code: str,
    *,
    now: int | None = None,
    ttl_seconds: int = DEFAULT_TOKEN_TTL_SECONDS,
) -> str:
    if ttl_seconds <= 0:
        raise ValueError("ttl_seconds must be positive.")

    timestamp = int(time.time() if now is None else now)
    expires_at = timestamp + ttl_seconds

    return urlencode(
        {
            "exp": str(expires_at),
            "sig": sign(code, expires_at),
        }
    )


def verify(
    code: str,
    expires_at: str,
    signature: str,
    *,
    now: int | None = None,
) -> bool:
    try:
        exp = int(expires_at)
    except (TypeError, ValueError):
        return False

    timestamp = int(time.time() if now is None else now)

    if exp < timestamp:
        return False

    # Do not accept arbitrarily long-lived bearer URLs even if a caller
    # accidentally signs one. This bounds replay after URL disclosure.
    if exp - timestamp > DEFAULT_TOKEN_TTL_SECONDS:
        return False

    expected = sign(code, exp)
    return hmac.compare_digest(expected, signature)
