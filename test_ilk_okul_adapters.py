#!/usr/bin/env python3

from __future__ import annotations

import unittest
from unittest.mock import patch

import adapters
import gosterme_adapters
from gosterme_adapters.sites import (
    IlkOkulNativeAdapter as SiteIlkOkulNativeAdapter,
)


FAST_READING_HTML = """
<!doctype html>
<html>
<head><title>Fast Reading</title></head>
<body>
<div id="sahne1"></div>
<div id="sahne2" class="ortega"></div>
<div id="app"></div>
<div id="sonucsayfasi"><div class="result-card"></div></div>
<div id="app1"></div>
<div id="sonucsayfasi1"><div class="report-card"></div></div>
<div id="gecisAnimasyon"></div>
<div id="gecisAnimasyon2"></div>
</body>
</html>
"""


class IlkOkulAdapterTests(unittest.TestCase):
    def test_facade_uses_site_owned_implementation(self):
        self.assertTrue(
            issubclass(adapters.IlkOkulNativeAdapter, SiteIlkOkulNativeAdapter)
        )

    def test_fast_reading_uses_centralized_fetch_and_body_isolation(self):
        url = "https://ilk-okul.com/1912/hizliokuma/icerik/7harfli/"

        with patch.object(
            adapters,
            "fetch_html",
            return_value=(url, FAST_READING_HTML),
        ) as call:
            item = adapters.IlkOkulNativeAdapter().resolve(url)

        call.assert_called_once_with(
            url,
            allowed_hosts=adapters.IlkOkulNativeAdapter.SOURCE_HOSTS,
        )
        self.assertEqual(item.adapter, "ilk-okul-native")
        self.assertEqual(item.render_mode, "isolate")
        self.assertEqual(item.selector, "body")

    def test_partial_fingerprint_remains_not_applicable(self):
        url = "https://ilk-okul.com/example/"
        document = "<html><body><div id='sahne1'></div></body></html>"

        with patch.object(
            adapters,
            "fetch_html",
            return_value=(url, document),
        ):
            with self.assertRaises(adapters.NotApplicable):
                adapters.IlkOkulNativeAdapter().resolve(url)

    def test_context_path_uses_resolution_fetch(self):
        url = "https://ilk-okul.com/1912/hizliokuma/icerik/7harfli/"
        calls = []

        def fetch_html(source_url, allowed_hosts):
            calls.append((source_url, allowed_hosts))
            return url, FAST_READING_HTML

        context = gosterme_adapters.ResolutionContext(
            normalized_url=url,
            hostname=adapters.hostname(url),
            fetch_html=fetch_html,
        )

        with patch.object(
            adapters,
            "fetch_html",
            side_effect=AssertionError("legacy fetch path used"),
        ):
            item = gosterme_adapters.AdapterRegistry(
                [adapters.IlkOkulNativeAdapter()]
            ).resolve_context(context)

        self.assertEqual(item.adapter, "ilk-okul-native")
        self.assertEqual(item.render_mode, "isolate")
        self.assertEqual(item.selector, "body")
        self.assertEqual(
            calls,
            [(url, adapters.IlkOkulNativeAdapter.SOURCE_HOSTS)],
        )


if __name__ == "__main__":
    unittest.main()
