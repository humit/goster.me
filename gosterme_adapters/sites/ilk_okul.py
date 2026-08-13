"""ilk-okul.com native activity adapter."""

from __future__ import annotations

from collections.abc import Callable

from ..context import ResolutionContext
from ..html import NativeGameFingerprintParser
from ..types import NotApplicable, ResolvedContent


SOURCE_HOSTS = {
    "ilk-okul.com",
    "www.ilk-okul.com",
}


class IlkOkulNativeAdapter:
    name = "ilk-okul-native"
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
            raise NotApplicable("No supported İlk-Okul native game found.")

        return ResolvedContent(
            kind="native-exercise",
            provider="ilk-okul-native",
            source_url=url,
            title=parser.title,
            content_url=final_url,
            adapter=self.name,
            render_mode="isolate",
            selector=selector,
        )


def native_selector(ids: set[str], classes: set[str]) -> str | None:
    """Return the exact activity root for a conservative known family."""

    # Reading Race uses sibling screens and therefore requires the source body.
    if {
        "acilis",
        "metinon",
        "start",
        "basla",
        "metin",
        "finish",
        "sonuc",
        "result",
        "kelimesayisi",
        "okunankelime",
    }.issubset(ids):
        return "body"

    # Flying Words keeps every activity state under one stable container.
    if {
        "container",
        "speed-selector",
        "reading-speed",
        "reading-screen",
        "word",
        "speed-display",
        "okuma-ici-butonu",
        "okuma-sonu-mesaj",
        "performans-sonucu",
        "toplam-kelime",
    }.issubset(ids):
        return "#container"

    # Türkçesi Varken needs the landing and game screens inside .hero.
    if (
        {
            "landingScreen",
            "startGameBtn",
            "gameScreen",
            "gameCard",
            "progressText",
            "scoreText",
            "correctFlash",
        }.issubset(ids)
        and "hero" in classes
        and "game-shell" in classes
        and "question-card" in classes
    ):
        return ".hero"

    # Yazılanı Değil Rengi has sibling application states under body.container.
    if (
        {
            "sahne1",
            "basla",
            "sahne2",
            "oyunuyenile",
            "score",
            "sonuclar",
        }.issubset(ids)
        and {
            "questionblock",
            "soru",
            "cevaplar",
        }.issubset(classes)
    ):
        return "body.container"

    # Fast Reading exposes intro, game, result, report, and transitions as
    # siblings, so every state must remain available under the source body.
    if (
        {
            "sahne1",
            "sahne2",
            "app",
            "sonucsayfasi",
            "app1",
            "sonucsayfasi1",
            "gecisAnimasyon",
            "gecisAnimasyon2",
        }.issubset(ids)
        and {
            "ortega",
            "result-card",
            "report-card",
        }.issubset(classes)
    ):
        return "body"

    return None
