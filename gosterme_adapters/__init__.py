"""Stable adapter contracts and deterministic registry primitives."""

from .context import ResolutionContext
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
    "ResolutionContext",
    "ResolvedContent",
    "ResolveError",
    "UnsupportedURL",
]
