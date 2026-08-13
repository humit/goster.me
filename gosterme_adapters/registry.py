"""Deterministic source-ordered adapter resolution."""

from __future__ import annotations

from collections.abc import Callable, Sequence

from .context import ResolutionContext
from .types import ContentAdapter, NotApplicable, ResolvedContent, UnsupportedURL


class AdapterRegistry:
    """Resolve against adapters in their declared source order."""

    def __init__(self, adapters: Sequence[ContentAdapter]):
        self._adapters = adapters

    def matching_names(self, url: str) -> list[str]:
        return [adapter.name for adapter in self._adapters if adapter.match(url)]

    def resolve(
        self,
        url: str,
        *,
        hostname: Callable[[str], str],
    ) -> ResolvedContent:
        return self._resolve(url, unsupported_hostname=lambda: hostname(url))

    def resolve_context(self, context: ResolutionContext) -> ResolvedContent:
        """Resolve using the normalized data for one resolution attempt."""

        return self._resolve(
            context.normalized_url,
            unsupported_hostname=lambda: context.hostname,
        )

    def _resolve(
        self,
        url: str,
        *,
        unsupported_hostname: Callable[[], str],
    ) -> ResolvedContent:
        matched = False
        notes: list[str] = []

        for adapter in self._adapters:
            if not adapter.match(url):
                continue

            matched = True

            try:
                return adapter.resolve(url)
            except NotApplicable as exc:
                if str(exc):
                    notes.append(f"{adapter.name}: {exc}")

        if matched:
            details = "; ".join(notes)
            message = (
                "URL belongs to a known source, "
                "but no content adapter could resolve it."
            )
            if details:
                message += f" ({details})"
            raise UnsupportedURL(message)

        raise UnsupportedURL(f"No adapter supports host: {unsupported_hostname()}")
