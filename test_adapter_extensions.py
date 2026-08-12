#!/usr/bin/env python3

from __future__ import annotations

import unittest
from unittest.mock import patch

import adapter_extensions  # noqa: F401
import adapters


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


class IlkOkulExtensionTests(unittest.TestCase):
    def test_fast_reading_page_resolves_to_body_isolation(self):
        url = "https://ilk-okul.com/1912/hizliokuma/icerik/7harfli/"

        with patch.object(
            adapters,
            "fetch_html",
            return_value=(url, FAST_READING_HTML),
        ):
            item = adapters.IlkOkulNativeAdapter().resolve(url)

        self.assertEqual(item.adapter, "ilk-okul-native")
        self.assertEqual(item.render_mode, "isolate")
        self.assertEqual(item.selector, "body")

    def test_partial_fingerprint_remains_not_applicable(self):
        url = "https://ilk-okul.com/example/"
        html = "<html><body><div id='sahne1'></div></body></html>"

        with patch.object(
            adapters,
            "fetch_html",
            return_value=(url, html),
        ):
            with self.assertRaises(adapters.NotApplicable):
                adapters.IlkOkulNativeAdapter().resolve(url)


if __name__ == "__main__":
    unittest.main()
