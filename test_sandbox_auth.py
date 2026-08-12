#!/usr/bin/env python3

from __future__ import annotations

import unittest
from unittest.mock import patch
from urllib.parse import parse_qs

import sandbox_auth
import sandbox_app


TEST_KEY = "k" * 32


class SandboxAuthTests(unittest.TestCase):
    def test_round_trip_signature(self):
        with patch.dict(
            "os.environ",
            {"GOSTER_SANDBOX_SIGNING_KEY": TEST_KEY},
            clear=False,
        ):
            query = sandbox_auth.signed_query("abc346", now=100)
            values = parse_qs(query)
            self.assertTrue(
                sandbox_auth.verify(
                    "abc346",
                    values["exp"][0],
                    values["sig"][0],
                    now=100,
                )
            )

    def test_rejects_wrong_code_or_signature(self):
        with patch.dict(
            "os.environ",
            {"GOSTER_SANDBOX_SIGNING_KEY": TEST_KEY},
            clear=False,
        ):
            query = sandbox_auth.signed_query("abc346", now=100)
            values = parse_qs(query)
            self.assertFalse(
                sandbox_auth.verify(
                    "abc347",
                    values["exp"][0],
                    values["sig"][0],
                    now=100,
                )
            )
            self.assertFalse(
                sandbox_auth.verify(
                    "abc346",
                    values["exp"][0],
                    "0" * 64,
                    now=100,
                )
            )

    def test_rejects_expired_or_overlong_capability(self):
        with patch.dict(
            "os.environ",
            {"GOSTER_SANDBOX_SIGNING_KEY": TEST_KEY},
            clear=False,
        ):
            expired_sig = sandbox_auth.sign("abc346", 99)
            self.assertFalse(
                sandbox_auth.verify("abc346", "99", expired_sig, now=100)
            )

            long_exp = 100 + sandbox_auth.DEFAULT_TOKEN_TTL_SECONDS + 1
            long_sig = sandbox_auth.sign("abc346", long_exp)
            self.assertFalse(
                sandbox_auth.verify(
                    "abc346",
                    str(long_exp),
                    long_sig,
                    now=100,
                )
            )

    def test_missing_or_short_secret_fails_closed(self):
        with patch.dict("os.environ", {}, clear=True):
            with self.assertRaises(RuntimeError):
                sandbox_auth.sign("abc346", 200)

        with patch.dict(
            "os.environ",
            {"GOSTER_SANDBOX_SIGNING_KEY": "short"},
            clear=True,
        ):
            with self.assertRaises(RuntimeError):
                sandbox_auth.sign("abc346", 200)

    def test_sandbox_query_requires_exact_signed_fields(self):
        with patch.dict(
            "os.environ",
            {"GOSTER_SANDBOX_SIGNING_KEY": TEST_KEY},
            clear=False,
        ):
            query = sandbox_auth.signed_query("abc346")
            self.assertTrue(sandbox_app.valid_capability_query("abc346", query))
            self.assertFalse(sandbox_app.valid_capability_query("abc346", ""))
            self.assertFalse(
                sandbox_app.valid_capability_query(
                    "abc346",
                    query + "&extra=1",
                )
            )


if __name__ == "__main__":
    unittest.main()
