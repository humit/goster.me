#!/usr/bin/env python3

from __future__ import annotations

import io
import unittest
import urllib.parse
from types import SimpleNamespace
from unittest.mock import Mock, patch

import product_app


class ProductContactTests(unittest.TestCase):
    def test_home_uses_internal_contact_page(self):
        page = product_app.render_home()
        self.assertIn('href="/contact">İletişim</a>', page)
        self.assertNotIn("github.com/humit/goster.me/issues", page)

    def test_about_explains_first_party_measurement(self):
        page = product_app.render_about()
        self.assertIn("Ham IP adresi saklanmaz", page)
        self.assertIn("30 gün", page)

    def test_information_page_views_are_recorded_with_client_ip(self):
        for path, event in (("/about", "about_view"), ("/contact", "contact_view")):
            with self.subTest(path=path), patch.object(product_app.ANALYTICS, "record") as record:
                handler = product_app.Handler.__new__(product_app.Handler)
                handler.path = path
                handler.client_address = ("203.0.113.10", 12345)
                handler.headers = {}
                handler.send_html = Mock()

                handler.do_GET()

                record.assert_called_once_with(event, visitor_ip="203.0.113.10")
                handler.send_html.assert_called_once()

    def test_share_page_view_is_recorded_without_short_code(self):
        item = SimpleNamespace(
            provider="youtube", adapter="youtube", render_mode="youtube-embed"
        )
        with (
            patch.object(product_app.STORE, "get", return_value=item),
            patch.object(product_app.ANALYTICS, "record") as record,
        ):
            handler = product_app.Handler.__new__(product_app.Handler)
            handler.path = "/q/abc346"
            handler.client_address = ("203.0.113.10", 12345)
            handler.headers = {}
            handler.send_html = Mock()

            handler.do_GET()

            record.assert_called_once_with(
                "share_page_view",
                provider="youtube",
                adapter="youtube",
                render_mode="youtube-embed",
                visitor_ip="203.0.113.10",
            )

    def test_valid_unsupported_url_is_added_to_adapter_backlog(self):
        source_url = "https://example.com/activity/lesson?token=secret"
        body = urllib.parse.urlencode({"url": source_url}).encode()
        with (
            patch.object(product_app, "allow_resolve", return_value=True),
            patch.object(
                product_app,
                "hardened_resolve_url",
                side_effect=product_app.adapters.UnsupportedURL("unsupported"),
            ),
            patch.object(product_app.UNSUPPORTED, "record") as record,
            patch.object(product_app.ANALYTICS, "record"),
        ):
            handler = product_app.Handler.__new__(product_app.Handler)
            handler.path = "/resolve"
            handler.client_address = ("203.0.113.10", 12345)
            handler.headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Content-Length": str(len(body)),
            }
            handler.rfile = io.BytesIO(body)
            handler.send_html = Mock()

            handler.do_POST()

            record.assert_called_once_with(source_url)
            self.assertEqual(handler.send_html.call_args.args[0], 400)

    def test_contact_form_is_minimal_and_escapes_replayed_input(self):
        page = product_app.render_contact(
            category="suggestion",
            message='<script>alert("x")</script>',
            error="Tekrar deneyin.",
        )
        self.assertIn('action="/contact"', page)
        self.assertIn('type="hidden" name="form_token"', page)
        self.assertIn('value="suggestion" selected', page)
        self.assertIn('&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;', page)
        self.assertNotIn('<script>alert("x")</script>', page)
        self.assertNotIn('name="email"', page)
        self.assertNotIn('name="phone"', page)
        self.assertNotIn('name="name"', page)

    def test_feedback_form_token_is_signed_and_expires(self):
        token = product_app.issue_feedback_form_token(now=1_000_000)

        self.assertTrue(
            product_app.valid_feedback_form_token(token, now=1_000_001)
        )
        self.assertFalse(
            product_app.valid_feedback_form_token(token + "x", now=1_000_001)
        )
        self.assertFalse(
            product_app.valid_feedback_form_token(
                token,
                now=1_000_000 + product_app.FEEDBACK_FORM_TOKEN_TTL_SECONDS + 1,
            )
        )

    def test_private_origin_feedback_uses_signed_form_token(self):
        form_token = product_app.issue_feedback_form_token()
        body = urllib.parse.urlencode(
            {
                "category": "suggestion",
                "message": "Safari submission",
                "website": "",
                "form_token": form_token,
            }
        ).encode()
        with (
            patch.object(product_app, "allow_feedback", return_value=True),
            patch.object(product_app.FEEDBACK, "submit") as submit,
            patch.object(product_app.ANALYTICS, "record"),
        ):
            handler = product_app.Handler.__new__(product_app.Handler)
            handler.path = "/contact"
            handler.client_address = ("203.0.113.10", 12345)
            handler.headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Content-Length": str(len(body)),
                "Origin": "null",
            }
            handler.rfile = io.BytesIO(body)
            handler.redirect = Mock()
            handler.send_error = Mock()

            handler.do_POST()

            submit.assert_called_once_with("suggestion", "Safari submission")
            handler.redirect.assert_called_once_with("/contact/thanks")
            handler.send_error.assert_not_called()

    def test_invalid_form_token_is_rejected_before_rate_limit(self):
        body = urllib.parse.urlencode(
            {
                "category": "problem",
                "message": "Cross-site submission",
                "website": "",
                "form_token": "invalid",
            }
        ).encode()
        with patch.object(product_app, "allow_feedback") as allow_feedback:
            handler = product_app.Handler.__new__(product_app.Handler)
            handler.path = "/contact"
            handler.client_address = ("203.0.113.10", 12345)
            handler.headers = {
                "Content-Type": "application/x-www-form-urlencoded",
                "Content-Length": str(len(body)),
                "Origin": "null",
            }
            handler.rfile = io.BytesIO(body)
            handler.send_error = Mock()

            handler.do_POST()

            handler.send_error.assert_called_once_with(403)
            allow_feedback.assert_not_called()

    def test_cross_site_feedback_is_rejected(self):
        same_origin = SimpleNamespace(
            headers={"Origin": product_app.PUBLIC_ORIGIN, "Sec-Fetch-Site": "same-origin"}
        )
        private_same_origin = SimpleNamespace(
            headers={"Origin": "null", "Sec-Fetch-Site": "same-origin"}
        )
        cross_site = SimpleNamespace(
            headers={"Origin": "https://example.com", "Sec-Fetch-Site": "cross-site"}
        )
        self.assertTrue(product_app.same_origin_request(same_origin))
        self.assertTrue(product_app.same_origin_request(private_same_origin))
        self.assertFalse(product_app.same_origin_request(cross_site))

    def test_feedback_without_fetch_metadata_falls_back_to_origin(self):
        canonical = SimpleNamespace(headers={"Origin": product_app.PUBLIC_ORIGIN})
        unknown = SimpleNamespace(headers={"Origin": "null"})

        self.assertTrue(product_app.same_origin_request(canonical))
        self.assertFalse(product_app.same_origin_request(unknown))


if __name__ == "__main__":
    unittest.main()
