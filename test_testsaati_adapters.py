#!/usr/bin/env python3

from __future__ import annotations

import unittest
from unittest.mock import patch

import adapters
import gosterme_adapters
from gosterme_adapters.sites import (
    TestSaatiZombifyAdapter as SiteTestSaatiZombifyAdapter,
)
from gosterme_adapters.sites.testsaati import ZombifyFingerprintParser


class TestSaatiAdapterTests(unittest.TestCase):
    URL = "https://testsaati.com/quiz"

    def test_facade_uses_site_owned_implementation(self):
        self.assertTrue(
            issubclass(
                adapters.TestSaatiZombifyAdapter,
                SiteTestSaatiZombifyAdapter,
            )
        )
        self.assertIs(
            adapters.ExerciseFingerprintParser,
            ZombifyFingerprintParser,
        )

    def test_facade_uses_centralized_fetch_hook(self):
        document = (
            "<html><head><title>Zombify</title></head><body>"
            '<div class="zf-quiz zf-trivia_quiz"></div>'
            "</body></html>"
        )

        with patch.object(
            adapters,
            "fetch_html",
            return_value=(self.URL, document),
        ) as call:
            item = adapters.TestSaatiZombifyAdapter().resolve(self.URL)

        call.assert_called_once_with(
            self.URL,
            allowed_hosts=adapters.TestSaatiZombifyAdapter.SOURCE_HOSTS,
        )
        self.assertEqual(item.provider, "zombify")
        self.assertEqual(item.render_mode, "isolate")
        self.assertEqual(item.selector, ".zf-quiz")

    def test_data_attribute_fingerprint_remains_supported(self):
        document = (
            "<html><body>"
            '<div class="zf-quiz" data-quiz_type="personality"></div>'
            "</body></html>"
        )

        with patch.object(
            adapters,
            "fetch_html",
            return_value=(self.URL, document),
        ):
            item = adapters.TestSaatiZombifyAdapter().resolve(self.URL)

        self.assertEqual(item.selector, ".zf-quiz")

    def test_partial_fingerprints_remain_not_applicable(self):
        documents = (
            '<html><body><div class="zf-quiz"></div></body></html>',
            '<html><body><div class="zf-trivia_quiz"></div></body></html>',
            '<html><body><div data-quiz_type="trivia"></div></body></html>',
        )

        for document in documents:
            with self.subTest(document=document):
                with patch.object(
                    adapters,
                    "fetch_html",
                    return_value=(self.URL, document),
                ):
                    with self.assertRaises(adapters.NotApplicable):
                        adapters.TestSaatiZombifyAdapter().resolve(self.URL)

    def test_context_path_uses_resolution_fetch(self):
        document = (
            "<html><head><title>Zombify</title></head><body>"
            '<div class="zf-quiz zf-trivia_quiz"></div>'
            "</body></html>"
        )
        calls = []

        def fetch_html(source_url, allowed_hosts):
            calls.append((source_url, allowed_hosts))
            return self.URL, document

        context = gosterme_adapters.ResolutionContext(
            normalized_url=self.URL,
            hostname=adapters.hostname(self.URL),
            fetch_html=fetch_html,
        )

        with patch.object(
            adapters,
            "fetch_html",
            side_effect=AssertionError("legacy fetch path used"),
        ):
            item = gosterme_adapters.AdapterRegistry(
                [adapters.TestSaatiZombifyAdapter()]
            ).resolve_context(context)

        self.assertEqual(item.adapter, "testsaati-zombify")
        self.assertEqual(item.provider, "zombify")
        self.assertEqual(item.render_mode, "isolate")
        self.assertEqual(item.selector, ".zf-quiz")
        self.assertEqual(
            calls,
            [(self.URL, adapters.TestSaatiZombifyAdapter.SOURCE_HOSTS)],
        )


if __name__ == "__main__":
    unittest.main()
