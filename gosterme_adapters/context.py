"""Per-attempt adapter resolution state."""

from __future__ import annotations

from dataclasses import dataclass, field


@dataclass
class ResolutionContext:
    """Share derived and fetched data within one resolution attempt."""

    normalized_url: str
    hostname: str
    final_url: str | None = None
    document: str | None = None
    parser_results: dict[str, object] = field(default_factory=dict)
