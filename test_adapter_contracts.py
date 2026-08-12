from __future__ import annotations

import unittest

import adapters
import goster_adapters
from goster_adapters import types


class AdapterContractCompatibilityTests(unittest.TestCase):
    def test_package_exports_shared_contracts(self):
        self.assertIs(goster_adapters.ResolvedContent, types.ResolvedContent)
        self.assertIs(goster_adapters.AdapterError, types.AdapterError)
        self.assertIs(goster_adapters.UnsupportedURL, types.UnsupportedURL)
        self.assertIs(goster_adapters.ResolveError, types.ResolveError)
        self.assertIs(goster_adapters.NotApplicable, types.NotApplicable)
        self.assertIs(goster_adapters.ContentAdapter, types.ContentAdapter)

    @unittest.expectedFailure
    def test_legacy_module_reexports_package_contracts(self):
        # Migration guard: remove expectedFailure when adapters.py becomes
        # the compatibility facade for these package-owned contracts.
        self.assertIs(adapters.ResolvedContent, types.ResolvedContent)
        self.assertIs(adapters.AdapterError, types.AdapterError)
        self.assertIs(adapters.UnsupportedURL, types.UnsupportedURL)
        self.assertIs(adapters.ResolveError, types.ResolveError)
        self.assertIs(adapters.NotApplicable, types.NotApplicable)
        self.assertIs(adapters.ContentAdapter, types.ContentAdapter)


if __name__ == "__main__":
    unittest.main()
