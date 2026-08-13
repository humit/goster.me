#!/usr/bin/env python3

from __future__ import annotations

import unittest
from unittest.mock import patch

import adapters
import gosterme_adapters
from gosterme_adapters.html import BasicHTMLParser
from gosterme_adapters.providers import (
    GenericWordwallPageAdapter as ProviderGenericWordwallPageAdapter,
    WordwallDirectAdapter as ProviderWordwallDirectAdapter,
    YouTubeAdapter as ProviderYouTubeAdapter,
)


class ProviderOwnershipTests(unittest.TestCase):
    def test_facade_classes_use_provider_owned_implementations(self):
        self.assertTrue(issubclass(adapters.YouTubeAdapter, ProviderYouTubeAdapter))
        self.assertTrue(
            issubclass(adapters.WordwallDirectAdapter, ProviderWordwallDirectAdapter)
        )
        self.assertTrue(
            issubclass(
                adapters.GenericWordwallPageAdapter,
                ProviderGenericWordwallPageAdapter,
            )
        )
        self.assertIs(adapters.BasicHTMLParser, BasicHTMLParser)

    def test_youtube_facade_uses_runtime_normalizer(self):
        normalized = "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        with patch.object(adapters, "normalized_url", return_value=normalized) as call:
            item = adapters.YouTubeAdapter().resolve("https://example.com/raw")

        call.assert_called_once_with("https://example.com/raw")
        self.assertEqual(item.source_url, normalized)
        self.assertEqual(item.adapter, "youtube")

    def test_wordwall_facade_uses_centralized_fetch_hook(self):
        url = "https://ilkokulderslerim.com/activity"
        document = (
            "<html><head><title>Fixture</title></head><body>"
            '<iframe src="https://wordwall.net/embed/one"></iframe>'
            "</body></html>"
        )
        with patch.object(
            adapters,
            "fetch_html",
            return_value=(url, document),
        ) as call:
            item = adapters.GenericWordwallPageAdapter().resolve(url)

        call.assert_called_once_with(
            url,
            allowed_hosts=adapters.GenericWordwallPageAdapter.SOURCE_HOSTS,
        )
        self.assertEqual(item.content_url, "https://wordwall.net/embed/one")
        self.assertEqual(item.render_mode, "embed")

    def test_wordwall_context_fetch_is_shared_with_fallback(self):
        url = "https://ilkokulderslerim.com/activity"
        document = "<html><head><title>Fixture</title></head><body></body></html>"
        calls = []

        def fetch_html(source_url, allowed_hosts):
            calls.append((source_url, allowed_hosts))
            return url, document

        wordwall = ProviderGenericWordwallPageAdapter(
            normalize_url=adapters.normalized_url,
            hostname=adapters.hostname,
            fetch_html=lambda _url, _hosts: self.fail(
                "legacy fetch path used"
            ),
        )

        class FallbackAdapter:
            name = "fallback"

            def match(self, source_url):
                return True

            def resolve(self, source_url):
                raise AssertionError("legacy resolver used")

            def resolve_context(self, context):
                final_url, _document = context.fetch(
                    ProviderGenericWordwallPageAdapter.SOURCE_HOSTS
                )
                return adapters.ResolvedContent(
                    kind="native-exercise",
                    provider="fixture",
                    source_url=context.normalized_url,
                    content_url=final_url,
                    adapter=self.name,
                )

        context = gosterme_adapters.ResolutionContext(
            normalized_url=url,
            hostname=adapters.hostname(url),
            fetch_html=fetch_html,
        )
        item = gosterme_adapters.AdapterRegistry(
            [wordwall, FallbackAdapter()]
        ).resolve_context(context)

        self.assertEqual(item.adapter, "fallback")
        self.assertEqual(
            calls,
            [
                (
                    url,
                    ProviderGenericWordwallPageAdapter.SOURCE_HOSTS,
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
