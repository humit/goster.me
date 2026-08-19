#!/usr/bin/env python3

from __future__ import annotations

import unittest
from unittest.mock import patch

import ilkokulakademi_discovery as discovery
from adapters import ResolvedContent, UnsupportedURL


class IlkokulAkademiDiscoveryTests(unittest.TestCase):
    def test_discovers_same_site_post_urls_only(self):
        html = """
        <a href="/2026/08/example-one.html">one</a>
        <a href="https://www.ilkokulakademi.com/2025/12/example-two.html?x=1#top">two</a>
        <a href="/p/sitemap.html">page</a>
        <a href="/search/label/Oyunlar">label</a>
        <a href="https://example.com/2026/08/external.html">external</a>
        <a href="/2026/08/example-one.html">duplicate</a>
        """

        self.assertEqual(
            discovery.discover_post_urls(html),
            [
                "https://www.ilkokulakademi.com/2026/08/example-one.html",
                "https://www.ilkokulakademi.com/2025/12/example-two.html",
            ],
        )

    def test_discovers_blogger_older_index_url(self):
        html = """
        <a href="/search?max-results=7">current</a>
        <a href="/search?max-results=7&amp;updated-max=2025-12-10T12%3A52%3A00%2B03%3A00">older</a>
        """

        self.assertEqual(
            discovery.discover_older_index_url(
                html,
                base_url="https://www.ilkokulakademi.com/search?max-results=7",
            ),
            "https://www.ilkokulakademi.com/search?max-results=7&updated-max=2025-12-10T12%3A52%3A00%2B03%3A00",
        )

    def test_discover_urls_follows_pagination_until_limit(self):
        first = """
        <a href="/2026/08/a.html">a</a>
        <a href="/2026/08/b.html">b</a>
        <a href="/search?max-results=50&amp;updated-max=2026-08-01T00%3A00%3A00%2B03%3A00">older</a>
        """
        second_url = (
            "https://www.ilkokulakademi.com/search?max-results=50&"
            "updated-max=2026-08-01T00%3A00%3A00%2B03%3A00"
        )
        second = """
        <a href="/2026/07/c.html">c</a>
        <a href="/2026/07/d.html">d</a>
        """

        def fake_fetch(url, *, allowed_hosts):
            self.assertEqual(allowed_hosts, discovery.ALLOWED_HOSTS)
            if url == discovery.INDEX_URL:
                return url, first
            if url == second_url:
                return url, second
            raise AssertionError(url)

        with patch.object(discovery, "fetch_html", side_effect=fake_fetch) as fetch_html:
            urls = discovery.discover_urls(limit=3, max_pages=5)

        self.assertEqual(
            urls,
            [
                "https://www.ilkokulakademi.com/2026/08/a.html",
                "https://www.ilkokulakademi.com/2026/08/b.html",
                "https://www.ilkokulakademi.com/2026/07/c.html",
            ],
        )
        self.assertEqual(fetch_html.call_count, 2)

    def test_fingerprint_collects_gameish_ids_classes_and_iframe_hosts(self):
        html = """
        <div id="exam-panel-wrapper" class="quiz-shell layout">
            <div id="start-screen" class="start-card"></div>
            <div id="question-text" class="question-box"></div>
            <iframe src="https://wordwall.net/embed/example"></iframe>
        </div>
        """

        fingerprint = discovery.discovery_fingerprint(
            html,
            base_url="https://www.ilkokulakademi.com/2026/08/example.html",
        )

        self.assertIn("id:exam-panel-wrapper", fingerprint)
        self.assertIn("id:start-screen", fingerprint)
        self.assertIn("id:question-text", fingerprint)
        self.assertIn("class:quiz-shell", fingerprint)
        self.assertIn("class:start-card", fingerprint)
        self.assertIn("class:question-box", fingerprint)
        self.assertIn("iframe:wordwall.net", fingerprint)
        self.assertNotIn("class:layout", fingerprint)

    def test_inspect_url_reports_current_resolver_result(self):
        url = "https://www.ilkokulakademi.com/2026/08/example.html"
        result = ResolvedContent(
            kind="native-exercise",
            provider="ilkokulakademi-native",
            source_url=url,
            title="Example",
            content_url=url,
            adapter="ilkokulakademi-native",
            render_mode="isolate",
            selector="#exam-panel-wrapper",
        )
        html = '<div id="exam-panel-wrapper"><div id="start-screen"></div></div>'

        with (
            patch.object(discovery, "matching_adapters", return_value=["ilkokulakademi-native"]),
            patch.object(discovery, "resolve_url", return_value=result),
            patch.object(discovery, "fetch_html", return_value=(url, html)) as fetch_html,
        ):
            record = discovery.inspect_url(url)

        self.assertEqual(record.status, "resolved")
        self.assertEqual(record.adapter, "ilkokulakademi-native")
        self.assertEqual(record.selector, "#exam-panel-wrapper")
        fetch_html.assert_called_once_with(
            url,
            allowed_hosts=discovery.ALLOWED_HOSTS,
        )

    def test_known_unresolved_keeps_discovery_fingerprint(self):
        url = "https://www.ilkokulakademi.com/2026/08/unknown.html"
        html = """
        <div id="mystery-game">
            <div id="question-zone" class="answer-grid"></div>
        </div>
        """

        with (
            patch.object(discovery, "matching_adapters", return_value=["ilkokulakademi-native"]),
            patch.object(discovery, "resolve_url", side_effect=UnsupportedURL("No adapter matched.")),
            patch.object(discovery, "fetch_html", return_value=(url, html)),
        ):
            record = discovery.inspect_url(url)

        self.assertEqual(record.status, "known-unresolved")
        self.assertIn("id:mystery-game", record.fingerprint)
        self.assertIn("id:question-zone", record.fingerprint)
        self.assertIn("class:answer-grid", record.fingerprint)


if __name__ == "__main__":
    unittest.main()
