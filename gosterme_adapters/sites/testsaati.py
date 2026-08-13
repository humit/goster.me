"""TestSaati native activity adapter."""

from __future__ import annotations

from collections.abc import Callable

from ..context import ResolutionContext
from ..html import BasicHTMLParser
from ..types import NotApplicable, ResolvedContent


SOURCE_HOSTS = {
    "testsaati.com",
    "www.testsaati.com",
}


class ZombifyFingerprintParser(BasicHTMLParser):
    """Detect the conservative Zombify quiz fingerprint."""

    def __init__(self):
        super().__init__()
        self.has_zombify_quiz = False

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        attrs = dict(attrs)
        classes = set(attrs.get("class", "").split())

        if (
            "zf-quiz" in classes
            and (
                "zf-trivia_quiz" in classes
                or attrs.get("data-quiz_type")
            )
        ):
            self.has_zombify_quiz = True


class TestSaatiZombifyAdapter:
    name = "testsaati-zombify"
    SOURCE_HOSTS = SOURCE_HOSTS

    def __init__(
        self,
        *,
        normalize_url: Callable[[str], str],
        hostname: Callable[[str], str],
        fetch_html: Callable[[str, set[str]], tuple[str, str]],
    ):
        self._normalize_url = normalize_url
        self._hostname = hostname
        self._fetch_html = fetch_html

    def match(self, url: str) -> bool:
        return self._hostname(url) in self.SOURCE_HOSTS

    def resolve(self, url: str) -> ResolvedContent:
        url = self._normalize_url(url)

        if not self.match(url):
            raise NotApplicable()

        return self._resolve_document(
            url,
            *self._fetch_html(url, self.SOURCE_HOSTS),
        )

    def resolve_context(
        self,
        context: ResolutionContext,
    ) -> ResolvedContent:
        url = context.normalized_url

        if not self.match(url):
            raise NotApplicable()

        return self._resolve_document(
            url,
            *context.fetch(self.SOURCE_HOSTS),
        )

    def _resolve_document(
        self,
        url: str,
        final_url: str,
        document: str,
    ) -> ResolvedContent:
        parser = ZombifyFingerprintParser()
        parser.feed(document)

        if not parser.has_zombify_quiz:
            raise NotApplicable("No Zombify quiz found.")

        return ResolvedContent(
            kind="native-exercise",
            provider="zombify",
            source_url=url,
            title=parser.title,
            content_url=final_url,
            adapter=self.name,
            render_mode="isolate",
            selector=".zf-quiz",
        )
