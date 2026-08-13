#!/usr/bin/env python3

from __future__ import annotations

import os
import unittest
from unittest.mock import patch
from urllib.error import HTTPError
from urllib.request import Request

from security import (
    AllowlistRedirectHandler,
    SecurityValidationError,
    public_origin,
    validate_public_origin,
    validate_public_url,
    validated_youtube_video_id,
    _redirect_allowed_hosts,
)


class URLValidationTests(unittest.TestCase):
    def test_accepts_normal_https_url(self):
        self.assertEqual(
            validate_public_url("https://example.com/path?q=1"),
            "https://example.com/path?q=1",
        )

    def test_rejects_non_http_scheme(self):
        with self.assertRaises(SecurityValidationError):
            validate_public_url("file:///etc/passwd")

    def test_rejects_credentials(self):
        with self.assertRaises(SecurityValidationError):
            validate_public_url("https://user:pass@example.com/path")

    def test_rejects_nonstandard_port(self):
        with self.assertRaises(SecurityValidationError):
            validate_public_url("https://example.com:8443/path")

    def test_rejects_ipv4_literal(self):
        with self.assertRaises(SecurityValidationError):
            validate_public_url("http://127.0.0.1/admin")

    def test_rejects_ipv6_literal(self):
        with self.assertRaises(SecurityValidationError):
            validate_public_url("http://[::1]/admin")

    def test_rejects_legacy_numeric_ipv4_forms(self):
        values = (
            "https://234555/",
            "https://2130706433/",
            "https://127.1/",
            "https://0177.0.0.1/",
            "https://0x7f.0.0.1/",
        )

        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(SecurityValidationError):
                    validate_public_url(value)

    def test_rejects_single_label_and_invalid_dns_hosts(self):
        values = (
            "https://localhost/",
            "https://server/",
            "https://bad_host.example/",
            "https://-bad.example/",
            "https://bad-.example/",
            "https://example.123/",
        )

        for value in values:
            with self.subTest(value=value):
                with self.assertRaises(SecurityValidationError):
                    validate_public_url(value)

    def test_accepts_multilabel_dns_and_idn_hosts(self):
        values = (
            "https://example.com/",
            "https://subdomain.example.com/path",
            "https://example.com./path",
            "https://xn--bcher-kva.example/path",
            "https://bücher.example/path",
        )

        for value in values:
            with self.subTest(value=value):
                self.assertEqual(validate_public_url(value), value)

    def test_rejects_control_characters(self):
        with self.assertRaises(SecurityValidationError):
            validate_public_url("https://example.com/a\nb")

    def test_rejects_oversized_url(self):
        with self.assertRaises(SecurityValidationError):
            validate_public_url("https://example.com/" + ("a" * 4096))


class OriginValidationTests(unittest.TestCase):
    def test_accepts_origin(self):
        self.assertEqual(
            validate_public_origin("https://goster.me/"),
            "https://goster.me",
        )

    def test_rejects_origin_path(self):
        with self.assertRaises(SecurityValidationError):
            validate_public_origin("https://goster.me/evil")

    def test_environment_origin(self):
        with patch.dict(
            os.environ,
            {"GOSTER_PUBLIC_ORIGIN": "https://stage.goster.me"},
        ):
            self.assertEqual(public_origin(), "https://stage.goster.me")


class YouTubeValidationTests(unittest.TestCase):
    def test_accepts_standard_video_id(self):
        self.assertEqual(
            validated_youtube_video_id("dQw4w9WgXcQ"),
            "dQw4w9WgXcQ",
        )

    def test_rejects_path_injection(self):
        self.assertIsNone(
            validated_youtube_video_id("../evil/path")
        )

    def test_rejects_wrong_length(self):
        self.assertIsNone(
            validated_youtube_video_id("short")
        )


class RedirectValidationTests(unittest.TestCase):
    def setUp(self):
        self.handler = AllowlistRedirectHandler()
        self.request = Request("https://example.com/start")

    def test_blocks_redirect_to_unlisted_host_before_open(self):
        token = _redirect_allowed_hosts.set(frozenset({"example.com"}))

        try:
            with self.assertRaises(HTTPError):
                self.handler.redirect_request(
                    self.request,
                    None,
                    302,
                    "Found",
                    {},
                    "http://127.0.0.1/internal",
                )
        finally:
            _redirect_allowed_hosts.reset(token)

    def test_blocks_redirect_to_different_public_host(self):
        token = _redirect_allowed_hosts.set(frozenset({"example.com"}))

        try:
            with self.assertRaises(HTTPError):
                self.handler.redirect_request(
                    self.request,
                    None,
                    302,
                    "Found",
                    {},
                    "https://attacker.example/path",
                )
        finally:
            _redirect_allowed_hosts.reset(token)


if __name__ == "__main__":
    unittest.main()
