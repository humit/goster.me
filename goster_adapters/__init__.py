"""Modular adapter implementation for goster.me.

The top-level ``adapters`` module remains the public compatibility facade while
implementation is migrated here incrementally.
"""

from .types import (
    AdapterError,
    ContentAdapter,
    NotApplicable,
    ResolveError,
    ResolvedContent,
    UnsupportedURL,
)

__all__ = [
    "AdapterError",
    "ContentAdapter",
    "NotApplicable",
    "ResolveError",
    "ResolvedContent",
    "UnsupportedURL",
]
