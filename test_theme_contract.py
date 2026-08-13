#!/usr/bin/env python3

from __future__ import annotations

import unittest

from unittest.mock import Mock, patch

import product_app


def relative_luminance(color: str) -> float:
    channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        value / 12.92
        if value <= 0.04045
        else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def contrast_ratio(foreground: str, background: str) -> float:
    lighter, darker = sorted(
        (relative_luminance(foreground), relative_luminance(background)),
        reverse=True,
    )
    return (lighter + 0.05) / (darker + 0.05)


class ThemeContractTests(unittest.TestCase):
    def test_default_and_optional_themes_are_allowlisted(self):
        for theme in product_app.THEME_META_COLORS:
            with self.subTest(theme=theme), patch.dict(
                "os.environ", {"GOSTER_THEME": theme}
            ):
                page = product_app.render_home()
                self.assertIn(f'data-theme="{theme}"', page)

        with patch.dict("os.environ", {"GOSTER_THEME": 'bad" theme'}):
            page = product_app.render_home()

        self.assertIn('data-theme="default"', page)
        self.assertNotIn('bad" theme', page)

    def test_theme_color_metadata_tracks_selected_palette(self):
        with patch.dict("os.environ", {"GOSTER_THEME": "april-23"}):
            page = product_app.render_about()

        self.assertIn(
            '<meta name="theme-color" content="#fff8f8" '
            'media="(prefers-color-scheme: light)">',
            page,
        )
        self.assertIn(
            '<meta name="theme-color" content="#160d0f" '
            'media="(prefers-color-scheme: dark)">',
            page,
        )

    def test_every_registered_theme_has_static_css_tokens(self):
        stylesheet = (product_app.STATIC_DIR / "product.css").read_text()

        for theme in product_app.THEME_META_COLORS:
            if theme == "default":
                continue
            with self.subTest(theme=theme):
                self.assertGreaterEqual(
                    stylesheet.count(f':root[data-theme="{theme}"]'),
                    2,
                )

        self.assertNotIn("/static/themes.css", product_app.render_home())

    def test_theme_text_tokens_meet_wcag_aa_contrast(self):
        stylesheets = (product_app.STATIC_DIR / "product.css").read_text()
        palette_pairs = (
            ("#626b65", "#f7f7f4"),
            ("#267b71", "#f7f7f4"),
            ("#16312e", "#9ad2ca"),
            ("#a0aaa4", "#0b0d10"),
            ("#8bcac0", "#0b0d10"),
            ("#102825", "#8bcac0"),
            ("#706164", "#fff8f8"),
            ("#b31522", "#fff8f8"),
            ("#4d0a10", "#f3a4aa"),
            ("#5f6d64", "#f5f8f5"),
            ("#2f7651", "#f5f8f5"),
            ("#173326", "#b7d8c3"),
            ("#626260", "#f5f5f2"),
            ("#8c3036", "#f5f5f2"),
            ("#3a1214", "#d8b5b6"),
            ("#c4a8ad", "#160d0f"),
            ("#ffadb4", "#160d0f"),
            ("#41080e", "#ef9aa1"),
            ("#a5b5aa", "#0b120e"),
            ("#a9d8b8", "#0b120e"),
            ("#102b1d", "#9bc9aa"),
            ("#adadaa", "#0c0c0c"),
            ("#dfaaad", "#0c0c0c"),
            ("#321012", "#c9a1a3"),
        )

        for foreground, background in palette_pairs:
            with self.subTest(foreground=foreground, background=background):
                self.assertIn(foreground, stylesheets)
                self.assertIn(background, stylesheets)
                self.assertGreaterEqual(
                    contrast_ratio(foreground, background),
                    4.5,
                )

    def test_all_product_pages_share_the_active_theme(self):
        with patch.dict("os.environ", {"GOSTER_THEME": "new-year"}):
            pages = (
                product_app.render_home(),
                product_app.render_about(),
                product_app.render_contact(),
                product_app.render_feedback_received(),
                product_app.render_security_error("Unsupported", "Message"),
            )

        for page in pages:
            self.assertIn('data-theme="new-year"', page)

    def test_viewer_stylesheet_is_allowlisted(self):
        for name in ("viewer-controls.css",):
            with self.subTest(name=name):
                handler = product_app.Handler.__new__(product_app.Handler)
                handler.send_bytes = Mock()

                self.assertTrue(handler.send_static(name))
                handler.send_bytes.assert_called_once()
                self.assertEqual(handler.send_bytes.call_args.args[0], 200)
                self.assertEqual(
                    handler.send_bytes.call_args.args[2],
                    "text/css; charset=utf-8",
                )


if __name__ == "__main__":
    unittest.main()
