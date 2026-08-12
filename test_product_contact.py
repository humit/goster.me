#!/usr/bin/env python3

from __future__ import annotations

import unittest
from types import SimpleNamespace

import product_app


class ProductContactTests(unittest.TestCase):
    def test_home_uses_internal_contact_page(self):
        page = product_app.render_home()
        self.assertIn('href="/contact">İletişim</a>', page)
        self.assertNotIn("github.com/humit/goster.me/issues", page)

    def test_contact_form_is_minimal_and_escapes_replayed_input(self):
        page = product_app.render_contact(
            category="suggestion",
            message='<script>alert("x")</script>',
            error="Tekrar deneyin.",
        )
        self.assertIn('action="/contact"', page)
        self.assertIn('value="suggestion" selected', page)
        self.assertIn('&lt;script&gt;alert(&quot;x&quot;)&lt;/script&gt;', page)
        self.assertNotIn('<script>alert("x")</script>', page)
        self.assertNotIn('name="email"', page)
        self.assertNotIn('name="phone"', page)
        self.assertNotIn('name="name"', page)

    def test_cross_site_feedback_is_rejected(self):
        same_origin = SimpleNamespace(
            headers={"Origin": product_app.PUBLIC_ORIGIN, "Sec-Fetch-Site": "same-origin"}
        )
        cross_site = SimpleNamespace(
            headers={"Origin": "https://example.com", "Sec-Fetch-Site": "cross-site"}
        )
        self.assertTrue(product_app.same_origin_request(same_origin))
        self.assertFalse(product_app.same_origin_request(cross_site))


if __name__ == "__main__":
    unittest.main()
