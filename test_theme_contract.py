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

    def test_static_asset_urls_are_content_versioned(self):
        page = product_app.product_document(
            "Example",
            "<main>Example</main>",
            viewer_controls=True,
        )

        for name in product_app.STATIC_ASSET_NAMES:
            with self.subTest(name=name):
                url = product_app.static_asset_url(name)
                prefix = f"/static/{name}?v="
                self.assertTrue(url.startswith(prefix))
                version = url.removeprefix(prefix)
                self.assertEqual(len(version), 12)
                int(version, 16)
                self.assertIn(url, page)

    def test_versioned_static_asset_route_ignores_hash_query(self):
        handler = product_app.Handler.__new__(product_app.Handler)
        handler.path = product_app.static_asset_url("viewer-controls.css")

        with patch.object(handler, "send_static", return_value=True) as send:
            handler.do_GET()

        send.assert_called_once_with(
            "viewer-controls.css",
            "v=" + product_app.STATIC_ASSET_VERSIONS["viewer-controls.css"],
        )

    def test_exact_content_versions_are_cached_as_immutable(self):
        for name, version in product_app.STATIC_ASSET_VERSIONS.items():
            with self.subTest(name=name):
                handler = product_app.Handler.__new__(product_app.Handler)
                handler.send_bytes = Mock()

                self.assertTrue(handler.send_static(name, f"v={version}"))
                self.assertEqual(
                    handler.send_bytes.call_args.kwargs["cache_control"],
                    "public, max-age=31536000, immutable",
                )

    def test_unversioned_or_mismatched_assets_keep_short_cache(self):
        name = "product.css"
        version = product_app.STATIC_ASSET_VERSIONS[name]

        for query in ("", "v=stale", f"v={version}&extra=1"):
            with self.subTest(query=query):
                handler = product_app.Handler.__new__(product_app.Handler)
                handler.send_bytes = Mock()

                self.assertTrue(handler.send_static(name, query))
                self.assertEqual(
                    handler.send_bytes.call_args.kwargs["cache_control"],
                    "public, max-age=300",
                )

    def test_viewer_panel_uses_the_active_accent_palette(self):
        product_styles = (product_app.STATIC_DIR / "product.css").read_text()
        viewer_styles = (
            product_app.STATIC_DIR / "viewer-controls.css"
        ).read_text()

        self.assertIn("--g-viewer-panel: var(--g-accent);", product_styles)
        self.assertIn("--g-viewer-text: var(--g-accent-ink);", product_styles)
        self.assertIn("--g-viewer-muted: var(--g-accent-ink);", product_styles)
        self.assertIn("--g-viewer-control: rgba(0, 0, 0, .09);", product_styles)
        self.assertIn(
            "--g-viewer-control-border: color-mix(",
            product_styles,
        )
        self.assertIn(
            "@supports (color: color-mix(",
            product_styles,
        )
        self.assertIn(
            "border: 1px solid rgba(0, 0, 0, .28);",
            viewer_styles,
        )
        self.assertIn(
            "@supports (color: color-mix(",
            viewer_styles,
        )
        self.assertIn(
            "background: var(--g-viewer-control-hover);",
            viewer_styles,
        )
        self.assertIn(
            "border: 1px solid var(--g-viewer-control-border);",
            viewer_styles,
        )
        self.assertNotIn("rgba(12, 14, 18, .96)", product_styles)
        self.assertNotIn("rgba(255, 255, 255, .14)", viewer_styles)


if __name__ == "__main__":
    unittest.main()
