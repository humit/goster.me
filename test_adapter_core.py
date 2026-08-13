#!/usr/bin/env python3

from __future__ import annotations

import unittest
from unittest.mock import patch

import adapters
import gosterme_adapters


class CompatibilityFacadeTests(unittest.TestCase):
    def test_public_contracts_keep_identity(self):
        for name in (
            "ResolvedContent",
            "AdapterError",
            "UnsupportedURL",
            "ResolveError",
            "NotApplicable",
            "ContentAdapter",
            "ResolutionContext",
        ):
            self.assertIs(getattr(adapters, name), getattr(gosterme_adapters, name))

    def test_facade_uses_runtime_normalizer_and_patchable_registry(self):
        resolved = adapters.ResolvedContent(
            kind="embed",
            provider="fixture",
            source_url="https://example.com/normalized",
        )

        class FixtureAdapter:
            name = "fixture"

            def match(self, url):
                return url == "https://example.com/normalized"

            def resolve(self, url):
                self.resolved_url = url
                return resolved

        fixture = FixtureAdapter()
        with (
            patch.object(
                adapters,
                "normalized_url",
                return_value="https://example.com/normalized",
            ) as normalize,
            patch.object(adapters, "ADAPTERS", [fixture]),
        ):
            self.assertIs(adapters.resolve_url("https://example.com/raw"), resolved)

        normalize.assert_called_once_with("https://example.com/raw")
        self.assertEqual(fixture.resolved_url, "https://example.com/normalized")

    def test_facade_creates_one_context_from_normalized_url(self):
        resolved = adapters.ResolvedContent(
            kind="embed",
            provider="fixture",
            source_url="https://example.com/normalized",
        )

        with (
            patch.object(
                adapters,
                "normalized_url",
                return_value="https://example.com/normalized",
            ) as normalize,
            patch.object(adapters, "hostname", return_value="example.com") as host,
            patch.object(
                adapters.AdapterRegistry,
                "resolve_context",
                return_value=resolved,
            ) as resolve_context,
        ):
            self.assertIs(adapters.resolve_url("https://example.com/raw"), resolved)

        normalize.assert_called_once_with("https://example.com/raw")
        host.assert_called_once_with("https://example.com/normalized")
        context = resolve_context.call_args.args[0]
        self.assertEqual(
            context,
            adapters.ResolutionContext(
                normalized_url="https://example.com/normalized",
                hostname="example.com",
            ),
        )


class ResolutionContextTests(unittest.TestCase):
    def test_context_holds_per_attempt_resolution_data(self):
        context = gosterme_adapters.ResolutionContext(
            normalized_url="https://example.com/activity",
            hostname="example.com",
        )

        self.assertEqual(context.normalized_url, "https://example.com/activity")
        self.assertEqual(context.hostname, "example.com")
        self.assertIsNone(context.final_url)
        self.assertIsNone(context.document)
        self.assertEqual(context.parser_results, {})

        context.final_url = "https://www.example.com/activity"
        context.document = "<html></html>"
        context.parser_results["activity"] = {"selector": "#game"}

        self.assertEqual(context.final_url, "https://www.example.com/activity")
        self.assertEqual(context.document, "<html></html>")
        self.assertEqual(
            context.parser_results,
            {"activity": {"selector": "#game"}},
        )

    def test_parser_results_are_isolated_between_attempts(self):
        first = gosterme_adapters.ResolutionContext(
            normalized_url="https://example.com/first",
            hostname="example.com",
        )
        second = gosterme_adapters.ResolutionContext(
            normalized_url="https://example.com/second",
            hostname="example.com",
        )

        first.parser_results["fixture"] = object()

        self.assertEqual(second.parser_results, {})


class AdapterRegistryTests(unittest.TestCase):
    def test_declared_order_is_authoritative(self):
        calls = []

        class Candidate:
            def __init__(self, name, result=None):
                self.name = name
                self.result = result

            def match(self, _url):
                calls.append(("match", self.name))
                return True

            def resolve(self, _url):
                calls.append(("resolve", self.name))
                if self.result is None:
                    raise adapters.NotApplicable(self.name)
                return self.result

        result = adapters.ResolvedContent(
            kind="embed",
            provider="fixture",
            source_url="https://example.com",
        )
        registry = gosterme_adapters.AdapterRegistry(
            [Candidate("first"), Candidate("second", result)]
        )

        self.assertIs(
            registry.resolve("https://example.com", hostname=lambda _url: "example.com"),
            result,
        )
        self.assertEqual(
            calls,
            [
                ("match", "first"),
                ("resolve", "first"),
                ("match", "second"),
                ("resolve", "second"),
            ],
        )

    def test_context_path_uses_cached_url_and_hostname(self):
        calls = []

        class Candidate:
            name = "fixture"

            def match(self, url):
                calls.append(url)
                return False

        context = gosterme_adapters.ResolutionContext(
            normalized_url="https://example.com/normalized",
            hostname="example.com",
        )
        registry = gosterme_adapters.AdapterRegistry([Candidate()])

        with self.assertRaisesRegex(
            adapters.UnsupportedURL,
            "No adapter supports host: example.com",
        ):
            registry.resolve_context(context)

        self.assertEqual(calls, ["https://example.com/normalized"])


if __name__ == "__main__":
    unittest.main()
