#!/usr/bin/env python3

from __future__ import annotations

import unittest
from unittest.mock import patch

import adapters
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


if __name__ == "__main__":
    unittest.main()
