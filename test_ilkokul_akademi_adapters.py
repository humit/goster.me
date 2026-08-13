#!/usr/bin/env python3

from __future__ import annotations

import unittest
from unittest.mock import patch

import adapters
import gosterme_adapters
from gosterme_adapters.html import NativeGameFingerprintParser
from gosterme_adapters.sites import (
    IlkokulAkademiGithubEmbedAdapter as SiteGithubEmbedAdapter,
    IlkokulAkademiNativeAdapter as SiteNativeAdapter,
)


class IlkokulAkademiOwnershipTests(unittest.TestCase):
    def test_facades_use_site_owned_implementations(self):
        self.assertTrue(
            issubclass(
                adapters.IlkokulAkademiGithubEmbedAdapter,
                SiteGithubEmbedAdapter,
            )
        )
        self.assertTrue(
            issubclass(adapters.IlkokulAkademiNativeAdapter, SiteNativeAdapter)
        )
        self.assertIs(
            adapters.NativeGameFingerprintParser,
            NativeGameFingerprintParser,
        )

    def test_github_embed_facade_uses_centralized_fetch_hook(self):
        url = "https://ilkokulakademi.com/activity"
        document = (
            "<html><head><title>Fixture</title></head><body>"
            '<iframe src="https://omerfarukkus.github.io/game/"></iframe>'
            "</body></html>"
        )
        with patch.object(
            adapters,
            "fetch_html",
            return_value=(url, document),
        ) as call:
            item = adapters.IlkokulAkademiGithubEmbedAdapter().resolve(url)

        call.assert_called_once_with(
            url,
            allowed_hosts=adapters.IlkokulAkademiGithubEmbedAdapter.SOURCE_HOSTS,
        )
        self.assertEqual(item.content_url, "https://omerfarukkus.github.io/game/")
        self.assertEqual(item.render_mode, "embed")

    def test_native_facade_uses_centralized_fetch_hook(self):
        url = "https://ilkokulakademi.com/activity"
        document = """
            <html><head><title>Fixture</title></head><body>
              <main id="math-game-container">
                <p id="question-text"></p>
                <p id="score-display"></p>
              </main>
            </body></html>
        """
        with patch.object(
            adapters,
            "fetch_html",
            return_value=(url, document),
        ) as call:
            item = adapters.IlkokulAkademiNativeAdapter().resolve(url)

        call.assert_called_once_with(
            url,
            allowed_hosts=adapters.IlkokulAkademiNativeAdapter.SOURCE_HOSTS,
        )
        self.assertEqual(item.selector, "#math-game-container")
        self.assertEqual(item.render_mode, "isolate")

    def test_context_fetch_is_shared_between_embed_and_native_adapters(self):
        url = "https://ilkokulakademi.com/activity"
        document = """
            <html><head><title>Fixture</title></head><body>
              <main id="math-game-container">
                <p id="question-text"></p>
                <p id="score-display"></p>
              </main>
            </body></html>
        """
        calls = []

        def fetch_html(source_url, allowed_hosts):
            calls.append((source_url, allowed_hosts))
            return url, document

        context = gosterme_adapters.ResolutionContext(
            normalized_url=url,
            hostname=adapters.hostname(url),
            fetch_html=fetch_html,
        )
        item = gosterme_adapters.AdapterRegistry(
            [
                adapters.IlkokulAkademiGithubEmbedAdapter(),
                adapters.IlkokulAkademiNativeAdapter(),
            ]
        ).resolve_context(context)

        self.assertEqual(item.adapter, "ilkokulakademi-native")
        self.assertEqual(item.selector, "#math-game-container")
        self.assertEqual(
            calls,
            [
                (
                    url,
                    adapters.IlkokulAkademiNativeAdapter.SOURCE_HOSTS,
                )
            ],
        )


if __name__ == "__main__":
    unittest.main()
