#!/usr/bin/env python3

from __future__ import annotations

import gzip
import threading
import time
from html.parser import HTMLParser
from io import BytesIO
from urllib.parse import parse_qs, urljoin, urlparse
from urllib.request import Request, urlopen

from gosterme_adapters import (
    AdapterError,
    AdapterRegistry,
    ContentAdapter,
    NotApplicable,
    ResolvedContent,
    ResolveError,
    UnsupportedURL,
)

USER_AGENT = "Mozilla/5.0 Childsafe/0.2"
MAX_HTML_BYTES = 2 * 1024 * 1024

HTML_CACHE_TTL = 120.0

_html_cache: dict[
    str,
    tuple[float, str, str],
] = {}

_html_cache_lock = threading.Lock()


def hostname(url: str) -> str:
    try:
        return (urlparse(url).hostname or "").lower()
    except ValueError:
        return ""


def normalized_url(url: str) -> str:
    value = url.strip()
    parsed = urlparse(value)

    if parsed.scheme not in {"http", "https"}:
        raise UnsupportedURL(
            "Only HTTP/HTTPS URLs are supported."
        )

    if not parsed.hostname:
        raise UnsupportedURL(
            "URL has no hostname."
        )

    return value


def fetch_html(
    url: str,
    allowed_hosts: set[str],
) -> tuple[str, str]:
    """
    Return:
        final_url, decoded_html

    Redirects are checked against the same allowlist.

    Recently fetched documents are cached briefly in memory so
    multiple adapters, or a renderer following resolution, do not
    immediately download the same source page again.
    """

    url = normalized_url(url)

    source_host = hostname(url)

    if source_host not in allowed_hosts:
        raise ResolveError(
            f"Host not allowed: {source_host}"
        )

    now = time.monotonic()

    with _html_cache_lock:
        cached = _html_cache.get(url)

    if cached is not None:
        cached_at, final_url, document = cached

        if (
            now - cached_at <= HTML_CACHE_TTL
            and hostname(final_url) in allowed_hosts
        ):
            return final_url, document

        with _html_cache_lock:
            _html_cache.pop(url, None)

    request = Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": (
                "text/html,"
                "application/xhtml+xml"
            ),
        },
    )

    try:
        with urlopen(
            request,
            timeout=15,
        ) as response:
            final_url = response.geturl()
            final_host = hostname(final_url)

            if final_host not in allowed_hosts:
                raise ResolveError(
                    "Redirected to disallowed host: "
                    f"{final_host}"
                )

            content_type = response.headers.get(
                "Content-Type",
                "",
            )

            if (
                "text/html"
                not in content_type.lower()
            ):
                raise ResolveError(
                    "Expected HTML, got: "
                    f"{content_type}"
                )

            content_encoding = (
                response.headers.get(
                    "Content-Encoding",
                    "",
                )
                .strip()
                .lower()
            )

            body = response.read(
                MAX_HTML_BYTES + 1
            )

            if len(body) > MAX_HTML_BYTES:
                raise ResolveError(
                    "Compressed HTML document "
                    "is too large."
                )

            if content_encoding == "gzip":
                try:
                    with gzip.GzipFile(
                        fileobj=BytesIO(body)
                    ) as gz:
                        body = gz.read(
                            MAX_HTML_BYTES + 1
                        )

                except OSError as exc:
                    raise ResolveError(
                        "Could not decompress gzip HTML: "
                        f"{exc}"
                    ) from exc

                if len(body) > MAX_HTML_BYTES:
                    raise ResolveError(
                        "Decompressed HTML document "
                        "is too large."
                    )

            elif content_encoding not in {
                "",
                "identity",
            }:
                raise ResolveError(
                    "Unsupported Content-Encoding: "
                    f"{content_encoding}"
                )

    except ResolveError:
        raise

    except Exception as exc:
        raise ResolveError(
            f"Could not fetch source page: {exc}"
        ) from exc

    document = body.decode(
        "utf-8",
        errors="replace",
    )

    with _html_cache_lock:
        _html_cache[url] = (
            time.monotonic(),
            final_url,
            document,
        )

    return final_url, document


class BasicHTMLParser(HTMLParser):
    def __init__(self):
        super().__init__()

        self.in_title = False
        self.title_parts: list[str] = []
        self.iframes: list[str] = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs = dict(attrs)

        if tag == "title":
            self.in_title = True

        elif tag == "iframe":
            src = (
                attrs.get("src")
                or attrs.get("data-lazy-src")
            )

            if src:
                self.iframes.append(src)

    def handle_endtag(self, tag):
        if tag.lower() == "title":
            self.in_title = False

    def handle_data(self, data):
        if not self.in_title:
            return

        value = data.strip()

        if value:
            self.title_parts.append(value)

    @property
    def title(self) -> str | None:
        value = " ".join(
            self.title_parts
        ).strip()

        return value or None


class ExerciseFingerprintParser(BasicHTMLParser):
    """
    Detect native exercise engines without changing the source DOM.

    This intentionally records only fingerprints. Rendering/isolation
    belongs to the Childsafe renderer, not the adapter.
    """

    def __init__(self):
        super().__init__()

        self.has_zombify_quiz = False

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)

        attrs = dict(attrs)

        classes = set(
            attrs.get("class", "").split()
        )

        if (
            "zf-quiz" in classes
            and (
                "zf-trivia_quiz" in classes
                or attrs.get("data-quiz_type")
            )
        ):
            self.has_zombify_quiz = True


class NativeGameFingerprintParser(BasicHTMLParser):
    """
    Collect stable DOM fingerprints for inline educational games.
    """

    def __init__(self):
        super().__init__()
        self.ids: set[str] = set()
        self.classes: set[str] = set()

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)

        attrs = dict(attrs)

        element_id = attrs.get("id")

        if element_id:
            self.ids.add(element_id)

        for cls in attrs.get("class", "").split():
            self.classes.add(cls)


class YouTubeAdapter:
    name = "youtube"

    HOSTS = {
        "youtube.com",
        "www.youtube.com",
        "m.youtube.com",
        "youtu.be",
    }

    def match(self, url: str) -> bool:
        return hostname(url) in self.HOSTS

    def video_id(
        self,
        url: str,
    ) -> str | None:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()

        if host == "youtu.be":
            return (
                parsed.path.strip("/").split("/")[0]
                or None
            )

        if parsed.path == "/watch":
            return parse_qs(
                parsed.query
            ).get(
                "v",
                [None],
            )[0]

        parts = [
            part
            for part in parsed.path.split("/")
            if part
        ]

        if (
            len(parts) >= 2
            and parts[0] in {
                "embed",
                "shorts",
                "live",
            }
        ):
            return parts[1]

        return None

    def resolve(
        self,
        url: str,
    ) -> ResolvedContent:
        url = normalized_url(url)

        if not self.match(url):
            raise NotApplicable()

        video_id = self.video_id(url)

        if not video_id:
            raise NotApplicable(
                "Could not determine YouTube video ID."
            )

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


class WordwallDirectAdapter:
    name = "wordwall-direct"

    HOSTS = {
        "wordwall.net",
        "www.wordwall.net",
    }

    def match(self, url: str) -> bool:
        return hostname(url) in self.HOSTS

    def resolve(
        self,
        url: str,
    ) -> ResolvedContent:
        url = normalized_url(url)

        if not self.match(url):
            raise NotApplicable()

        path = urlparse(url).path.lower()

        if "/embed/" not in path:
            raise NotApplicable(
                "Wordwall URL is not an embed."
            )

        return ResolvedContent(
            kind="embed",
            provider="wordwall",
            source_url=url,
            content_url=url,
            adapter=self.name,
        )


class GenericWordwallPageAdapter:
    name = "generic-wordwall-page"

    #
    # Real domains observed in the 1-A WhatsApp corpus.
    #
    SOURCE_HOSTS = {
        "egitimgen.com",
        "www.egitimgen.com",

        "ilkokulderslerim.com",
        "www.ilkokulderslerim.com",

        "ilkokulakademi.com",
        "www.ilkokulakademi.com",

        "ogretmeninihtiyaci.com",
        "www.ogretmeninihtiyaci.com",

        "testsaati.com",
        "www.testsaati.com",

        "ilkokulevim.com",
        "www.ilkokulevim.com",
    }

    WORDWALL_HOSTS = {
        "wordwall.net",
        "www.wordwall.net",
    }

    def match(self, url: str) -> bool:
        return hostname(url) in self.SOURCE_HOSTS

    def resolve(
        self,
        url: str,
    ) -> ResolvedContent:
        url = normalized_url(url)

        if not self.match(url):
            raise NotApplicable()

        final_url, document = fetch_html(
            url,
            allowed_hosts=self.SOURCE_HOSTS,
        )

        parser = BasicHTMLParser()
        parser.feed(document)

        candidates: list[str] = []

        for raw_src in parser.iframes:
            candidate = urljoin(
                final_url,
                raw_src,
            )

            candidate_host = hostname(
                candidate
            )

            if (
                candidate_host
                not in self.WORDWALL_HOSTS
            ):
                continue

            candidate_path = urlparse(
                candidate
            ).path.lower()

            if "/embed/" not in candidate_path:
                continue

            if candidate not in candidates:
                candidates.append(candidate)

        if not candidates:
            #
            # The source site itself is supported, but this
            # particular page is not a Wordwall page.
            #
            raise NotApplicable(
                "No Wordwall embed found."
            )

        if len(candidates) == 1:
            return ResolvedContent(
                kind="embed",
                provider="wordwall",
                source_url=url,
                title=parser.title,
                content_url=candidates[0],
                content_urls=tuple(candidates),
                adapter=self.name,
                render_mode="embed",
            )

        return ResolvedContent(
            kind="embed-collection",
            provider="wordwall",
            source_url=url,
            title=parser.title,
            #
            # Keep content_url for backward compatibility.
            #
            content_url=candidates[0],
            content_urls=tuple(candidates),
            adapter=self.name,
            render_mode="embed-collection",
        )


class IlkokulAkademiGithubEmbedAdapter:
    name = "ilkokulakademi-github-embed"

    SOURCE_HOSTS = {
        "ilkokulakademi.com",
        "www.ilkokulakademi.com",
    }

    #
    # Start conservatively with hosts actually observed in the
    # teacher-link corpus. Expand intentionally as new providers appear.
    #
    EMBED_HOSTS = {
        "omerfarukkus.github.io",
    }

    def match(self, url: str) -> bool:
        return hostname(url) in self.SOURCE_HOSTS

    def resolve(
        self,
        url: str,
    ) -> ResolvedContent:
        url = normalized_url(url)

        if not self.match(url):
            raise NotApplicable()

        final_url, document = fetch_html(
            url,
            allowed_hosts=self.SOURCE_HOSTS,
        )

        parser = BasicHTMLParser()
        parser.feed(document)

        for raw_src in parser.iframes:
            candidate = urljoin(
                final_url,
                raw_src,
            )

            if hostname(candidate) not in self.EMBED_HOSTS:
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

    SOURCE_HOSTS = {
        "ilkokulakademi.com",
        "www.ilkokulakademi.com",
    }

    def match(self, url: str) -> bool:
        return hostname(url) in self.SOURCE_HOSTS

    def resolve(
        self,
        url: str,
    ) -> ResolvedContent:
        url = normalized_url(url)

        if not self.match(url):
            raise NotApplicable()

        final_url, document = fetch_html(
            url,
            allowed_hosts=self.SOURCE_HOSTS,
        )

        parser = NativeGameFingerprintParser()
        parser.feed(document)

        ids = parser.ids
        classes = parser.classes

        #
        # Native-game families observed in the real WhatsApp corpus.
        #
        # Each family has a conservative fingerprint and an explicit
        # activity root. The renderer only needs the selector; the
        # source page keeps its original DOM/JS/CSS intact.
        #

        selector = None

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

        if any(
            required.issubset(ids)
            for required in game_container_families
        ):
            selector = "#game-container"

        elif (
            {
                "math-game-container",
                "question-text",
                "score-display",
            }.issubset(ids)
            or
            {
                "math-game-container",
                "question-text",
                "score-ui",
                "result-screen",
            }.issubset(ids)
        ):
            selector = "#math-game-container"

        elif {
            "game-wrapper",
            "screen-game",
            "screen-result",
            "question-text",
            "options-container",
            "score",
        }.issubset(ids):
            selector = "#game-wrapper"

        elif {
            "active-game-container",
            "game-card",
            "question-text",
            "options-container",
            "result-screen",
            "final-score",
        }.issubset(ids):
            selector = "#active-game-container"

        elif {
            "bilge-quiz-app",
            "bq-quiz-screen",
            "bq-question-text",
            "bq-options-container",
            "bq-result-screen",
        }.issubset(ids):
            selector = "#bilge-quiz-app"

        #
        # Turkish-named custom game families.
        #

        if selector is None and {
            "kurbaga-ana-konteynir",
            "soru-ekrani",
            "sonuc-ekrani",
            "soru-metni",
            "puan",
            "canlar",
        }.issubset(ids):
            selector = "#kurbaga-ana-konteynir"

        if selector is None and {
            "sincap-ana-konteynir-root",
            "sincap-ana-konteynir",
            "sincap-karakteri",
            "soru-ekrani",
            "sonuc-ekrani",
        }.issubset(ids):
            selector = "#sincap-ana-konteynir-root"

        if selector is None and (
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
            selector = ".sincap-etkinlik-alani"

        if selector is None and {
            "zipzip-area",
            "zipzip-score",
            "zipzip-over",
            "zv-result-title",
            "zv-result-score",
        }.issubset(ids):
            #
            # The Zipzip exercise does not expose a generic game-container
            # id, so isolate the smallest stable parent identified by the
            # source implementation.
            #
            selector = "#zipzip-area"

        if selector is None:
            raise NotApplicable(
                "No supported inline native game found."
            )

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


class IlkOkulNativeAdapter:
    name = "ilk-okul-native"

    SOURCE_HOSTS = {
        "ilk-okul.com",
        "www.ilk-okul.com",
    }

    def match(self, url: str) -> bool:
        return hostname(url) in self.SOURCE_HOSTS

    def resolve(
        self,
        url: str,
    ) -> ResolvedContent:
        url = normalized_url(url)

        if not self.match(url):
            raise NotApplicable()

        final_url, document = fetch_html(
            url,
            allowed_hosts=self.SOURCE_HOSTS,
        )

        parser = NativeGameFingerprintParser()
        parser.feed(document)

        ids = parser.ids
        classes = parser.classes

        selector = None

        #
        # Reading Race
        #
        # Observed corpus examples:
        #   /1912/hizliokuma/okuma-yarisi/...
        #
        # Keep the original DOM intact. The game uses multiple sibling
        # sections for intro, text, timing controls and results, so the
        # activity effectively occupies the source body.
        #
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
            selector = "body"

        #
        # Flying Words
        #
        # The whole interactive application is inside #container:
        # speed selection, reading screen, controls and completion state.
        #
        elif {
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
            selector = "#container"

        #
        # Türkçesi Varken
        #
        # .hero contains both #landingScreen and #gameScreen as well as
        # game feedback/audio. #gameScreen alone would lose the start UI.
        #
        elif (
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
            selector = ".hero"

        #
        # Yazılanı Değil Rengi
        #
        # Intro (#sahne1), game (#sahne2), questions and result table are
        # siblings directly under body.container. There is no smaller
        # stable common application root in the source page.
        #
        elif (
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
            selector = "body.container"

        if selector is None:
            raise NotApplicable(
                "No supported İlk-Okul native game found."
            )

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


class TestSaatiZombifyAdapter:
    name = "testsaati-zombify"

    SOURCE_HOSTS = {
        "testsaati.com",
        "www.testsaati.com",
    }

    def match(self, url: str) -> bool:
        return hostname(url) in self.SOURCE_HOSTS

    def resolve(
        self,
        url: str,
    ) -> ResolvedContent:
        url = normalized_url(url)

        if not self.match(url):
            raise NotApplicable()

        final_url, document = fetch_html(
            url,
            allowed_hosts=self.SOURCE_HOSTS,
        )

        parser = ExerciseFingerprintParser()
        parser.feed(document)

        if not parser.has_zombify_quiz:
            raise NotApplicable(
                "No Zombify quiz found."
            )

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


ADAPTERS: list[ContentAdapter] = [
    YouTubeAdapter(),
    WordwallDirectAdapter(),

    # Prefer clean third-party embeds before source-page isolation.
    GenericWordwallPageAdapter(),
    IlkokulAkademiGithubEmbedAdapter(),

    # Inline native educational applications.
    IlkokulAkademiNativeAdapter(),
    IlkOkulNativeAdapter(),

    # Native TestSaati/Zombify quizzes.
    TestSaatiZombifyAdapter(),
]


def resolve_url(
    url: str,
) -> ResolvedContent:
    url = normalized_url(url)
    return AdapterRegistry(ADAPTERS).resolve(url, hostname=hostname)


def matching_adapters(
    url: str,
) -> list[str]:
    url = normalized_url(url)
    return AdapterRegistry(ADAPTERS).matching_names(url)
