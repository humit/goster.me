"""Per-attempt adapter resolution state."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from urllib.parse import urlparse

from .types import ResolveError


FetchHTML = Callable[[str, set[str]], tuple[str, str]]


@dataclass
class ResolutionContext:
    """Share derived and fetched data within one resolution attempt."""

    normalized_url: str
    hostname: str
    fetch_html: FetchHTML | None = field(
        default=None,
        repr=False,
        compare=False,
    )
    final_url: str | None = None
    document: str | None = None
    parser_results: dict[str, object] = field(default_factory=dict)

    def fetch(self, allowed_hosts: set[str]) -> tuple[str, str]:
        """Fetch once and revalidate cached results for each adapter allowlist."""

        if self.hostname not in allowed_hosts:
            raise ResolveError(f"Host not allowed: {self.hostname}")

        if self.final_url is not None and self.document is not None:
            final_host = (urlparse(self.final_url).hostname or "").lower()
            if final_host not in allowed_hosts:
                raise ResolveError(
                    f"Redirected to disallowed host: {final_host}"
                )
            return self.final_url, self.document

        if self.final_url is not None or self.document is not None:
            raise RuntimeError("Resolution context has an incomplete fetch result.")

        if self.fetch_html is None:
            raise RuntimeError("Resolution context has no fetch function.")

        final_url, document = self.fetch_html(
            self.normalized_url,
            allowed_hosts,
        )
        final_host = (urlparse(final_url).hostname or "").lower()
        if final_host not in allowed_hosts:
            raise ResolveError(f"Redirected to disallowed host: {final_host}")

        self.final_url = final_url
        self.document = document
        return final_url, document
