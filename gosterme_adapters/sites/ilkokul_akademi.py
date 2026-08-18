"""İlkokul Akademi clean-embed and native activity adapters."""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urljoin

from ..context import ResolutionContext
from ..html import BasicHTMLParser, NativeGameFingerprintParser
from ..types import NotApplicable, ResolvedContent


SOURCE_HOSTS = {
    "ilkokulakademi.com",
    "www.ilkokulakademi.com",
}


class IlkokulAkademiGithubEmbedAdapter:
    name = "ilkokulakademi-github-embed"
    SOURCE_HOSTS = SOURCE_HOSTS

    # Expand only for hosts observed and reviewed in the teacher-link corpus.
    EMBED_HOSTS = {
        "omerfarukkus.github.io",
    }

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
        parser = BasicHTMLParser()
        parser.feed(document)

        for raw_src in parser.iframes:
            candidate = urljoin(final_url, raw_src)
            if self._hostname(candidate) not in self.EMBED_HOSTS:
                continue

            return ResolvedContent(
                kind="embed",
                provider="github-pages",
                source_url=url,
                title=parser.title,
                content_url=candidate,
                adapter=self.name,
                render_mode="embed",
            )

        raise NotApplicable(
            "No supported GitHub Pages exercise embed found."
        )


class IlkokulAkademiNativeAdapter:
    name = "ilkokulakademi-native"
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
        parser = NativeGameFingerprintParser()
        parser.feed(document)

        selector = native_selector(parser.ids, parser.classes)
        if selector is None:
            raise NotApplicable("No supported inline native game found.")

        return ResolvedContent(
            kind="native-exercise",
            provider="ilkokulakademi-native",
            source_url=url,
            title=parser.title,
            content_url=final_url,
            adapter=self.name,
            render_mode="isolate",
            selector=selector,
        )


def native_selector(ids: set[str], classes: set[str]) -> str | None:
    """Return the exact activity root for a conservative known family."""

    game_container_families = (
        {
            "game-container",
            "quiz-box",
            "question-text",
            "options-container",
            "score",
        },
        {
            "game-container",
            "question-box",
            "current-question",
            "score-display",
            "train-area",
        },
        {
            "game-container",
            "lives-display",
            "options-container",
            "score-display",
        },
        {
            "game-container",
            "game-screen",
            "result-screen",
            "options-container",
            "score-display",
        },
    )

    if any(required.issubset(ids) for required in game_container_families):
        return "#game-container"

    if (
        {
            "math-game-container",
            "question-text",
            "score-display",
        }.issubset(ids)
        or {
            "math-game-container",
            "question-text",
            "score-ui",
            "result-screen",
        }.issubset(ids)
    ):
        return "#math-game-container"

    if {
        "game-wrapper",
        "screen-game",
        "screen-result",
        "question-text",
        "options-container",
        "score",
    }.issubset(ids):
        return "#game-wrapper"

    if {
        "exam-panel-wrapper",
        "start-screen",
        "active-game-container",
        "game-card",
        "question-text",
        "options-container",
        "result-screen",
        "final-score",
    }.issubset(ids):
        return "#exam-panel-wrapper"

    if {
        "active-game-container",
        "game-card",
        "question-text",
        "options-container",
        "result-screen",
        "final-score",
    }.issubset(ids):
        return "#active-game-container"

    if {
        "bilge-quiz-app",
        "bq-quiz-screen",
        "bq-question-text",
        "bq-options-container",
        "bq-result-screen",
    }.issubset(ids):
        return "#bilge-quiz-app"

    if {
        "kurbaga-ana-konteynir",
        "soru-ekrani",
        "sonuc-ekrani",
        "soru-metni",
        "puan",
        "canlar",
    }.issubset(ids):
        return "#kurbaga-ana-konteynir"

    if {
        "sincap-ana-konteynir-root",
        "sincap-ana-konteynir",
        "sincap-karakteri",
        "soru-ekrani",
        "sonuc-ekrani",
    }.issubset(ids):
        return "#sincap-ana-konteynir-root"

    if (
        "sincap-etkinlik-alani" in classes
        and {
            "aktif-oyun",
            "oyun-sonu",
            "mevcut-soru",
            "oyuncu-sincap",
            "can-metni",
            "puan-metni",
        }.issubset(ids)
    ):
        return ".sincap-etkinlik-alani"

    if {
        "zipzip-area",
        "zipzip-score",
        "zipzip-over",
        "zv-result-title",
        "zv-result-score",
    }.issubset(ids):
        return "#zipzip-area"

    return None
