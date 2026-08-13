#!/usr/bin/env python3

from __future__ import annotations

import unittest

from io import BytesIO
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler
from pathlib import Path
from unittest.mock import Mock, patch

import product_app
import sandbox_app


def head_handler(handler_type, path):
    handler = handler_type.__new__(handler_type)
    handler.command = "HEAD"
    handler.path = path
    handler.request_version = "HTTP/1.1"
    handler.requestline = f"HEAD {path} HTTP/1.1"
    handler.client_address = ("203.0.113.10", 12345)
    handler.headers = {}
    handler.wfile = BytesIO()
    handler.log_request = Mock()
    return handler


class PublicWebStandardsTests(unittest.TestCase):
    def test_stable_pages_have_description_and_canonical_metadata(self):
        pages = (
            (product_app.render_home(), "https://goster.me/"),
            (product_app.render_about(), "https://goster.me/about"),
            (product_app.render_contact(), "https://goster.me/contact"),
        )

        for page, canonical in pages:
            with self.subTest(canonical=canonical):
                self.assertIn('<meta name="description" content="', page)
                self.assertIn(f'<link rel="canonical" href="{canonical}">', page)

    def test_primary_product_shell_has_no_inline_style(self):
        page = product_app.render_home()

        self.assertNotIn("<style>", page)
        self.assertIn(
            f'<link rel="stylesheet" href="{product_app.static_asset_url("product.css")}">',
            page,
        )

    def test_sitemap_contains_only_stable_indexable_pages(self):
        sitemap = product_app.sitemap_xml()

        self.assertIn("https://goster.me/</loc>", sitemap)
        self.assertIn("https://goster.me/about</loc>", sitemap)
        self.assertIn("https://goster.me/contact</loc>", sitemap)
        self.assertNotIn("/q/", sitemap)
        self.assertNotIn("/qr/", sitemap)

    def test_robots_is_advisory_and_points_to_sitemap(self):
        robots = product_app.robots_text()

        self.assertIn("User-agent: *", robots)
        self.assertIn("Disallow: /q/", robots)
        self.assertIn("Disallow: /qr/", robots)
        self.assertIn("Disallow: /v/", robots)
        self.assertIn("Sitemap: https://goster.me/sitemap.xml", robots)

    def test_security_txt_has_required_contact_expiry_and_canonical_fields(self):
        now = datetime(2026, 8, 13, tzinfo=timezone.utc)
        value = product_app.security_text(now=now)

        self.assertIn("Contact: https://goster.me/contact", value)
        self.assertIn("Expires: 2027-02-09T00:00:00Z", value)
        self.assertIn("Preferred-Languages: tr, en", value)
        self.assertIn(
            "Canonical: https://goster.me/.well-known/security.txt",
            value,
        )

    def test_public_standard_routes_have_explicit_content_types(self):
        expected = {
            "/robots.txt": "text/plain; charset=utf-8",
            "/sitemap.xml": "application/xml; charset=utf-8",
            "/.well-known/security.txt": "text/plain; charset=utf-8",
        }

        for path, content_type in expected.items():
            with self.subTest(path=path):
                handler = product_app.Handler.__new__(product_app.Handler)
                handler.path = path
                handler.send_bytes = Mock()

                handler.do_GET()

                handler.send_bytes.assert_called_once()
                self.assertEqual(handler.send_bytes.call_args.args[0], 200)
                self.assertEqual(handler.send_bytes.call_args.args[2], content_type)

    def test_dynamic_viewer_routes_emit_noindex_header(self):
        dynamic_paths = (
            "/abc346",
            "/q/abc346",
            "/qr/abc346.svg",
            "/g/abc346",
            "/v/abc346",
            "/contact/thanks",
            "/contact?from=abc346",
            "/resolve",
            "/api/events",
        )

        for path in dynamic_paths:
            with self.subTest(path=path):
                handler = product_app.Handler.__new__(product_app.Handler)
                handler.path = path
                headers = []

                with (
                    patch.object(
                        handler,
                        "send_header",
                        side_effect=lambda name, value: headers.append((name, value)),
                    ),
                    patch.object(BaseHTTPRequestHandler, "end_headers", return_value=None),
                ):
                    handler.end_headers()

                self.assertEqual(
                    dict(headers)["X-Robots-Tag"],
                    "noindex, nofollow, noarchive",
                )

    def test_stable_pages_do_not_emit_noindex_header(self):
        for path in ("/", "/about", "/contact"):
            with self.subTest(path=path):
                self.assertIsNone(product_app.robots_directive_for_target(path))

    def test_head_standard_routes_match_get_headers_without_a_body(self):
        expected = {
            "/robots.txt": "text/plain; charset=utf-8",
            "/sitemap.xml": "application/xml; charset=utf-8",
            "/.well-known/security.txt": "text/plain; charset=utf-8",
        }

        for path, content_type in expected.items():
            with self.subTest(path=path):
                handler = head_handler(product_app.Handler, path)
                handler.do_HEAD()
                response = handler.wfile.getvalue()
                headers, body = response.split(b"\r\n\r\n", 1)

                self.assertIn(b"HTTP/1.0 200 OK", headers)
                self.assertIn(f"Content-Type: {content_type}".encode(), headers)
                self.assertRegex(headers, rb"Content-Length: [1-9][0-9]*")
                self.assertEqual(body, b"")

    def test_head_home_has_no_body_or_analytics_side_effect(self):
        handler = head_handler(product_app.Handler, "/")

        with patch.object(product_app.ANALYTICS, "record") as record:
            handler.do_HEAD()

        headers, body = handler.wfile.getvalue().split(b"\r\n\r\n", 1)
        self.assertIn(b"HTTP/1.0 200 OK", headers)
        self.assertIn(b"Content-Type: text/html; charset=utf-8", headers)
        self.assertEqual(body, b"")
        record.assert_not_called()

    def test_head_viewer_preserves_noindex_without_touching_the_item(self):
        item = Mock(provider="youtube", adapter="youtube", render_mode="embed")
        handler = head_handler(product_app.Handler, "/abc346")

        with (
            patch.object(product_app.STORE, "get", return_value=item) as get,
            patch.object(product_app.ANALYTICS, "record") as record,
            patch.object(product_app.legacy, "render_child", return_value="viewer"),
        ):
            handler.do_HEAD()

        headers, body = handler.wfile.getvalue().split(b"\r\n\r\n", 1)
        self.assertIn(b"HTTP/1.0 200 OK", headers)
        self.assertIn(
            b"X-Robots-Tag: noindex, nofollow, noarchive",
            headers,
        )
        self.assertEqual(body, b"")
        get.assert_called_once_with("abc346", touch=False)
        record.assert_not_called()

    def test_caddy_example_exposes_only_sandbox_viewer_and_robots_routes(self):
        config = (
            Path(__file__).resolve().parent
            / "deploy/caddy-platform-hardening.Caddyfile.example"
        ).read_text()
        sandbox_block = config.split("s.goster.me {", 1)[1]

        self.assertIn("handle /robots.txt {", sandbox_block)
        self.assertIn("handle /v/* {", sandbox_block)
        self.assertIn("handle {\n        respond 404\n    }", sandbox_block)


class SandboxCrawlerPolicyTests(unittest.TestCase):
    def test_sandbox_robots_denies_all_crawlers(self):
        handler = sandbox_app.Handler.__new__(sandbox_app.Handler)
        handler.path = "/robots.txt"
        handler.send_text = Mock()

        handler.do_GET()

        handler.send_text.assert_called_once_with(
            200,
            "User-agent: *\nDisallow: /\n",
        )

    def test_every_sandbox_response_emits_noindex_header(self):
        handler = sandbox_app.Handler.__new__(sandbox_app.Handler)
        headers = []

        with (
            patch.object(
                handler,
                "send_header",
                side_effect=lambda name, value: headers.append((name, value)),
            ),
            patch.object(BaseHTTPRequestHandler, "end_headers", return_value=None),
        ):
            handler.end_headers()

        self.assertEqual(
            dict(headers)["X-Robots-Tag"],
            "noindex, nofollow, noarchive",
        )

    def test_head_robots_has_no_body_and_keeps_noindex(self):
        handler = head_handler(sandbox_app.Handler, "/robots.txt")
        handler.do_HEAD()

        headers, body = handler.wfile.getvalue().split(b"\r\n\r\n", 1)
        self.assertIn(b"HTTP/1.0 200 OK", headers)
        self.assertIn(b"Content-Type: text/plain; charset=utf-8", headers)
        self.assertIn(
            b"X-Robots-Tag: noindex, nofollow, noarchive",
            headers,
        )
        self.assertEqual(body, b"")


if __name__ == "__main__":
    unittest.main()
