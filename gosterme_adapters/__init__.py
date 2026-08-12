"""Stable adapter contracts and deterministic registry primitives."""

from .registry import AdapterRegistry
from .types import (
    AdapterError,
    ContentAdapter,
    NotApplicable,
    ResolvedContent,
    ResolveError,
    UnsupportedURL,
)

__all__ = [
    "AdapterError",
    "AdapterRegistry",
    "ContentAdapter",
    "NotApplicable",
    "ResolvedContent",
    "ResolveError",
    "UnsupportedURL",
]
