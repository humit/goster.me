#!/usr/bin/env python3

from __future__ import annotations

import unittest
from unittest.mock import patch

import adapters
import goster_adapters


class CompatibilityFacadeTests(unittest.TestCase):
    def test_public_contracts_keep_identity(self):
        for name in (
            "ResolvedContent",
            "AdapterError",
            "UnsupportedURL",
            "ResolveError",
            "NotApplicable",
            "ContentAdapter",
        ):
            self.assertIs(getattr(adapters, name), getattr(goster_adapters, name))

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
        registry = goster_adapters.AdapterRegistry(
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


if __name__ == "__main__":
    unittest.main()
