#!/usr/bin/env python3

from __future__ import annotations

import unittest
from unittest.mock import patch

import adapters
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


if __name__ == "__main__":
    unittest.main()
