#!/usr/bin/env python3

from __future__ import annotations

import gzip
import threading
import time
from io import BytesIO
from urllib.parse import urlparse
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
from gosterme_adapters.html import BasicHTMLParser, NativeGameFingerprintParser
from gosterme_adapters.providers import (
    GenericWordwallPageAdapter as ProviderGenericWordwallPageAdapter,
    WordwallDirectAdapter as ProviderWordwallDirectAdapter,
    YouTubeAdapter as ProviderYouTubeAdapter,
)
from gosterme_adapters.sites import (
    IlkOkulNativeAdapter as SiteIlkOkulNativeAdapter,
    IlkokulAkademiGithubEmbedAdapter as SiteIlkokulAkademiGithubEmbedAdapter,
    IlkokulAkademiNativeAdapter as SiteIlkokulAkademiNativeAdapter,
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


class YouTubeAdapter(ProviderYouTubeAdapter):
    """Compatibility facade using the runtime-hardened module hooks."""

    def __init__(self):
        super().__init__(
            normalize_url=lambda url: normalized_url(url),
            hostname=lambda url: hostname(url),
        )


class WordwallDirectAdapter(ProviderWordwallDirectAdapter):
    """Compatibility facade using the runtime-hardened module hooks."""

    def __init__(self):
        super().__init__(
            normalize_url=lambda url: normalized_url(url),
            hostname=lambda url: hostname(url),
        )


class GenericWordwallPageAdapter(ProviderGenericWordwallPageAdapter):
    """Compatibility facade using the centralized fetch path."""

    def __init__(self):
        super().__init__(
            normalize_url=lambda url: normalized_url(url),
            hostname=lambda url: hostname(url),
            fetch_html=lambda url, allowed_hosts: fetch_html(
                url,
                allowed_hosts=allowed_hosts,
            ),
        )


class IlkokulAkademiGithubEmbedAdapter(
    SiteIlkokulAkademiGithubEmbedAdapter
):
    """Compatibility facade using the centralized fetch path."""

    def __init__(self):
        super().__init__(
            normalize_url=lambda url: normalized_url(url),
            hostname=lambda url: hostname(url),
            fetch_html=lambda url, allowed_hosts: fetch_html(
                url,
                allowed_hosts=allowed_hosts,
            ),
        )


class IlkokulAkademiNativeAdapter(SiteIlkokulAkademiNativeAdapter):
    """Compatibility facade using the centralized fetch path."""

    def __init__(self):
        super().__init__(
            normalize_url=lambda url: normalized_url(url),
            hostname=lambda url: hostname(url),
            fetch_html=lambda url, allowed_hosts: fetch_html(
                url,
                allowed_hosts=allowed_hosts,
            ),
        )


class IlkOkulNativeAdapter(SiteIlkOkulNativeAdapter):
    """Compatibility facade using the centralized fetch path."""

    def __init__(self):
        super().__init__(
            normalize_url=lambda url: normalized_url(url),
            hostname=lambda url: hostname(url),
            fetch_html=lambda url, allowed_hosts: fetch_html(
                url,
                allowed_hosts=allowed_hosts,
            ),
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
