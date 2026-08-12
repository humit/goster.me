"""Direct and discovered Wordwall provider adapters."""

from __future__ import annotations

from collections.abc import Callable
from urllib.parse import urljoin, urlparse

from ..html import BasicHTMLParser
from ..types import NotApplicable, ResolvedContent


class WordwallDirectAdapter:
    name = "wordwall-direct"

    HOSTS = {
        "wordwall.net",
        "www.wordwall.net",
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

    def resolve(self, url: str) -> ResolvedContent:
        url = self._normalize_url(url)

        if not self.match(url):
            raise NotApplicable()

        if "/embed/" not in urlparse(url).path.lower():
            raise NotApplicable("Wordwall URL is not an embed.")

        return ResolvedContent(
            kind="embed",
            provider="wordwall",
            source_url=url,
            content_url=url,
            adapter=self.name,
        )


class GenericWordwallPageAdapter:
    name = "generic-wordwall-page"

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

        final_url, document = self._fetch_html(url, self.SOURCE_HOSTS)
        parser = BasicHTMLParser()
        parser.feed(document)

        candidates: list[str] = []
        for raw_src in parser.iframes:
            candidate = urljoin(final_url, raw_src)
            if self._hostname(candidate) not in self.WORDWALL_HOSTS:
                continue
            if "/embed/" not in urlparse(candidate).path.lower():
                continue
            if candidate not in candidates:
                candidates.append(candidate)

        if not candidates:
            raise NotApplicable("No Wordwall embed found.")

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
            content_url=candidates[0],
            content_urls=tuple(candidates),
            adapter=self.name,
            render_mode="embed-collection",
        )
