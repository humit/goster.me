"""Per-attempt adapter resolution state."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from typing import Literal, TypeVar, cast
from urllib.parse import urlparse

from .types import ResolveError


FetchHTML = Callable[[str, set[str]], tuple[str, str]]
ParserResult = TypeVar("ParserResult")
CandidateOutcome = Literal[
    "not-matched",
    "not-applicable",
    "resolved",
    "error",
]


@dataclass(frozen=True)
class CandidateTraceEntry:
    """Record one adapter outcome without public or source-content details."""

    adapter: str
    outcome: CandidateOutcome


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
    candidate_trace: list[CandidateTraceEntry] = field(
        default_factory=list,
        compare=False,
    )

    def trace_candidate(
        self,
        adapter: str,
        outcome: CandidateOutcome,
    ) -> None:
        """Append one deterministic registry outcome for diagnostics."""

        self.candidate_trace.append(
            CandidateTraceEntry(adapter=adapter, outcome=outcome)
        )

    def get_parser_result(
        self,
        key: str,
        factory: Callable[[], ParserResult],
    ) -> ParserResult:
        """Return one successful parser result per key and resolution attempt."""

        if key in self.parser_results:
            return cast(ParserResult, self.parser_results[key])

        result = factory()
        self.parser_results[key] = result
        return result

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
