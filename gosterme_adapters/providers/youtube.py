"""YouTube provider adapter."""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import parse_qs, urlparse

from ..types import NotApplicable, ResolvedContent


class YouTubeAdapter:
    name = "youtube"

    HOSTS = {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
    }

    def __init__(
        self,
        *,
        normalize_url: Callable[[str], str],
        hostname: Callable[[str], str],
    ):
        self._normalize_url = normalize_url
        self._hostname = hostname

    def match(self, url: str) -> bool:
        return self._hostname(url) in self.HOSTS

    def video_id(self, url: str) -> str | None:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()

        if host == "youtu.be":
            return parsed.path.strip("/").split("/")[0] or None

        if parsed.path == "/watch":
            return parse_qs(parsed.query).get("v", [None])[0]

        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"embed", "shorts", "live"}:
            return parts[1]

        return None

    def resolve(self, url: str) -> ResolvedContent:
        url = self._normalize_url(url)

        if not self.match(url):
            raise NotApplicable()

        video_id = self.video_id(url)
        if not video_id:
            raise NotApplicable("Could not determine YouTube video ID.")

        content_url = (
            "https://www.youtube-nocookie.com/embed/"
            + video_id
            + "?autoplay=0"
            + "&playsinline=1"
            + "&rel=0"
            + "&enablejsapi=1"
            + "&iv_load_policy=3"
            + "&hl=tr"
        )

        return ResolvedContent(
            kind="video",
            provider="youtube",
            source_url=url,
            content_url=content_url,
            adapter=self.name,
            render_mode="youtube-embed",
        )
