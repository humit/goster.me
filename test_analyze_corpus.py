#!/usr/bin/env python3

from __future__ import annotations

import importlib.util
import unittest
from importlib.machinery import SourceFileLoader
from pathlib import Path
from unittest.mock import patch

from adapters import ResolvedContent


SCRIPT = Path(__file__).with_name("analyze-corpus")


def load_analyzer():
    loader = SourceFileLoader("analyze_corpus_tool", str(SCRIPT))
    spec = importlib.util.spec_from_loader(loader.name, loader)
    module = importlib.util.module_from_spec(spec)
    loader.exec_module(module)
    return module


class AnalyzeCorpusTests(unittest.TestCase):
    def test_domain_exclusion_treats_www_and_bare_forms_as_equivalent(self):
        analyzer = load_analyzer()
        excluded = {"example.com"}

        self.assertTrue(
            analyzer.excluded_by_domain(
                "https://www.example.com/activity",
                excluded,
            )
        )
        self.assertTrue(
            analyzer.excluded_by_domain(
                "https://example.com/activity",
                excluded,
            )
        )
        self.assertFalse(
            analyzer.excluded_by_domain(
                "https://other.example/activity",
                excluded,
            )
        )

    def test_resolved_record_preserves_all_content_urls(self):
        analyzer = load_analyzer()
        source_url = "https://example.com/activity"
        content_urls = (
            "https://example.com/embed/one",
            "https://example.com/embed/two",
        )
        resolved = ResolvedContent(
            kind="embed-collection",
            provider="example",
            source_url=source_url,
            title="Fixture",
            content_url=content_urls[0],
            content_urls=content_urls,
            adapter="example-collection",
            render_mode="embed-collection",
        )

        with (
            patch.object(analyzer, "matching_adapters", return_value=[]),
            patch.object(analyzer, "resolve_url", return_value=resolved),
        ):
            record = analyzer.resolve_record(source_url)

        self.assertEqual(record["content_url"], content_urls[0])
        self.assertEqual(record["content_urls"], list(content_urls))
        self.assertEqual(record["title"], "Fixture")


if __name__ == "__main__":
    unittest.main()
