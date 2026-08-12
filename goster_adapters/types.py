from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Protocol


@dataclass(frozen=True)
class ResolvedContent:
    kind: str
    provider: str
    source_url: str
    title: str | None = None
    content_url: str | None = None
    content_urls: tuple[str, ...] = ()
    adapter: str | None = None

    # Rendering hints for Childsafe.
    render_mode: str | None = None
    selector: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


class AdapterError(RuntimeError):
    pass


class UnsupportedURL(AdapterError):
    pass


class ResolveError(AdapterError):
    pass


class NotApplicable(AdapterError):
    """
    The adapter recognizes the URL/site, but the page does not contain
    the content type handled by this adapter.

    This is not a fatal error. The resolver should try the next adapter.
    """

    pass


class ContentAdapter(Protocol):
    name: str

    def match(self, url: str) -> bool:
        ...

    def resolve(self, url: str) -> ResolvedContent:
        ...
