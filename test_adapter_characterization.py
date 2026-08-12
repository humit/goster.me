#!/usr/bin/env python3

from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import adapter_extensions
import adapters
from shortlinks import ShortLinkStore


def html_document(*, ids=(), classes=(), iframes=(), title="Fixture") -> str:
    elements = [f'<div id="{value}"></div>' for value in ids]
    elements.extend(f'<div class="{value}"></div>' for value in classes)
    elements.extend(f'<iframe src="{value}"></iframe>' for value in iframes)
    return (
        "<!doctype html><html><head>"
        f"<title>{title}</title></head><body>"
        + "".join(elements)
        + "</body></html>"
    )


class RegistryCharacterizationTests(unittest.TestCase):
    def test_registry_order_is_exact(self):
        self.assertEqual(
            [adapter.name for adapter in adapters.ADAPTERS],
            [
                "youtube",
                "wordwall-direct",
                "generic-wordwall-page",
                "ilkokulakademi-github-embed",
                "ilkokulakademi-native",
                "ilk-okul-native",
                "testsaati-zombify",
            ],
        )

    def test_same_site_candidates_prefer_embeds_before_native(self):
        self.assertEqual(
            adapters.matching_adapters("https://ilkokulakademi.com/example"),
            [
                "generic-wordwall-page",
                "ilkokulakademi-github-embed",
                "ilkokulakademi-native",
            ],
        )

    def test_not_applicable_falls_through_but_resolve_error_does_not(self):
        result = adapters.ResolvedContent(
            kind="embed",
            provider="fixture",
            source_url="https://example.com/source",
            content_url="https://example.com/embed",
            adapter="second",
            render_mode="embed",
        )

        class First:
            name = "first"

            def match(self, _url):
                return True

            def resolve(self, _url):
                raise adapters.NotApplicable("near miss")

        class Second:
            name = "second"

            def match(self, _url):
                return True

            def resolve(self, _url):
                return result

        with patch.object(adapters, "ADAPTERS", [First(), Second()]):
            self.assertIs(adapters.resolve_url("https://example.com"), result)

        class Broken(First):
            def resolve(self, _url):
                raise adapters.ResolveError("fetch failed")

        with patch.object(adapters, "ADAPTERS", [Broken(), Second()]):
            with self.assertRaisesRegex(adapters.ResolveError, "fetch failed"):
                adapters.resolve_url("https://example.com")


class ProviderAdapterCharacterizationTests(unittest.TestCase):
    def test_youtube_output_is_stable(self):
        item = adapters.YouTubeAdapter().resolve(
            "https://www.youtube.com/watch?v=dQw4w9WgXcQ"
        )
        self.assertEqual(
            item.to_dict(),
            {
                "kind": "video",
                "provider": "youtube",
                "source_url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "title": None,
                "content_url": (
                    "https://www.youtube-nocookie.com/embed/dQw4w9WgXcQ"
                    "?autoplay=0&playsinline=1&rel=0&enablejsapi=1"
                    "&iv_load_policy=3&hl=tr"
                ),
                "content_urls": (),
                "adapter": "youtube",
                "render_mode": "youtube-embed",
                "selector": None,
            },
        )

    def test_wordwall_direct_current_output_is_recorded(self):
        url = "https://wordwall.net/embed/abc123"
        item = adapters.WordwallDirectAdapter().resolve(url)
        self.assertEqual(item.kind, "embed")
        self.assertEqual(item.provider, "wordwall")
        self.assertEqual(item.content_url, url)
        self.assertEqual(item.adapter, "wordwall-direct")
        self.assertIsNone(item.render_mode)

    def test_wordwall_page_single_and_collection_outputs(self):
        url = "https://ilkokulderslerim.com/activity"
        adapter = adapters.GenericWordwallPageAdapter()

        single_html = html_document(
            iframes=("https://wordwall.net/embed/one",), title="Single"
        )
        with patch.object(adapters, "fetch_html", return_value=(url, single_html)):
            single = adapter.resolve(url)
        self.assertEqual(single.render_mode, "embed")
        self.assertEqual(single.content_url, "https://wordwall.net/embed/one")
        self.assertEqual(single.content_urls, ("https://wordwall.net/embed/one",))

        collection_html = html_document(
            iframes=(
                "https://wordwall.net/embed/one",
                "https://www.wordwall.net/embed/two",
                "https://wordwall.net/embed/one",
            ),
            title="Collection",
        )
        with patch.object(
            adapters, "fetch_html", return_value=(url, collection_html)
        ):
            collection = adapter.resolve(url)
        self.assertEqual(collection.kind, "embed-collection")
        self.assertEqual(collection.render_mode, "embed-collection")
        self.assertEqual(collection.content_url, "https://wordwall.net/embed/one")
        self.assertEqual(
            collection.content_urls,
            (
                "https://wordwall.net/embed/one",
                "https://www.wordwall.net/embed/two",
            ),
        )

    def test_wordwall_page_rejects_non_embed_iframes(self):
        url = "https://egitimgen.com/example"
        page = html_document(
            iframes=(
                "https://wordwall.net/resource/123",
                "https://example.net/embed/not-wordwall",
            )
        )
        with patch.object(adapters, "fetch_html", return_value=(url, page)):
            with self.assertRaises(adapters.NotApplicable):
                adapters.GenericWordwallPageAdapter().resolve(url)

    def test_ilkokulakademi_github_embed_is_allowlisted(self):
        url = "https://ilkokulakademi.com/example"
        page = html_document(
            iframes=(
                "https://untrusted.github.io/game/",
                "https://omerfarukkus.github.io/game/",
            )
        )
        with patch.object(adapters, "fetch_html", return_value=(url, page)):
            item = adapters.IlkokulAkademiGithubEmbedAdapter().resolve(url)
        self.assertEqual(item.provider, "github-pages")
        self.assertEqual(item.content_url, "https://omerfarukkus.github.io/game/")
        self.assertEqual(item.render_mode, "embed")


class IlkokulAkademiNativeCharacterizationTests(unittest.TestCase):
    URL = "https://ilkokulakademi.com/native"

    FAMILIES = (
        (
            {"game-container", "quiz-box", "question-text", "options-container", "score"},
            set(),
            "#game-container",
        ),
        (
            {"game-container", "question-box", "current-question", "score-display", "train-area"},
            set(),
            "#game-container",
        ),
        (
            {"game-container", "lives-display", "options-container", "score-display"},
            set(),
            "#game-container",
        ),
        (
            {"game-container", "game-screen", "result-screen", "options-container", "score-display"},
            set(),
            "#game-container",
        ),
        (
            {"math-game-container", "question-text", "score-display"},
            set(),
            "#math-game-container",
        ),
        (
            {"math-game-container", "question-text", "score-ui", "result-screen"},
            set(),
            "#math-game-container",
        ),
        (
            {"game-wrapper", "screen-game", "screen-result", "question-text", "options-container", "score"},
            set(),
            "#game-wrapper",
        ),
        (
            {"active-game-container", "game-card", "question-text", "options-container", "result-screen", "final-score"},
            set(),
            "#active-game-container",
        ),
        (
            {"bilge-quiz-app", "bq-quiz-screen", "bq-question-text", "bq-options-container", "bq-result-screen"},
            set(),
            "#bilge-quiz-app",
        ),
        (
            {"kurbaga-ana-konteynir", "soru-ekrani", "sonuc-ekrani", "soru-metni", "puan", "canlar"},
            set(),
            "#kurbaga-ana-konteynir",
        ),
        (
            {"sincap-ana-konteynir-root", "sincap-ana-konteynir", "sincap-karakteri", "soru-ekrani", "sonuc-ekrani"},
            set(),
            "#sincap-ana-konteynir-root",
        ),
        (
            {"aktif-oyun", "oyun-sonu", "mevcut-soru", "oyuncu-sincap", "can-metni", "puan-metni"},
            {"sincap-etkinlik-alani"},
            ".sincap-etkinlik-alani",
        ),
        (
            {"zipzip-area", "zipzip-score", "zipzip-over", "zv-result-title", "zv-result-score"},
            set(),
            "#zipzip-area",
        ),
    )

    def resolve(self, ids, classes=()):
        page = html_document(ids=ids, classes=classes)
        with patch.object(adapters, "fetch_html", return_value=(self.URL, page)):
            return adapters.IlkokulAkademiNativeAdapter().resolve(self.URL)

    def test_all_known_families_resolve_to_exact_selector(self):
        for ids, classes, selector in self.FAMILIES:
            with self.subTest(selector=selector, ids=sorted(ids)):
                item = self.resolve(ids, classes)
                self.assertEqual(item.kind, "native-exercise")
                self.assertEqual(item.adapter, "ilkokulakademi-native")
                self.assertEqual(item.render_mode, "isolate")
                self.assertEqual(item.selector, selector)

    def test_each_family_rejects_a_required_token_near_miss(self):
        for ids, classes, selector in self.FAMILIES:
            with self.subTest(selector=selector, ids=sorted(ids)):
                if classes:
                    reduced_ids = ids
                    reduced_classes = set()
                else:
                    reduced_ids = set(ids)
                    reduced_ids.remove(sorted(reduced_ids)[0])
                    reduced_classes = classes
                with self.assertRaises(adapters.NotApplicable):
                    self.resolve(reduced_ids, reduced_classes)


class IlkOkulNativeCharacterizationTests(unittest.TestCase):
    URL = "https://ilk-okul.com/native"

    FAMILIES = (
        (
            {"acilis", "metinon", "start", "basla", "metin", "finish", "sonuc", "result", "kelimesayisi", "okunankelime"},
            set(),
            "body",
        ),
        (
            {"container", "speed-selector", "reading-speed", "reading-screen", "word", "speed-display", "okuma-ici-butonu", "okuma-sonu-mesaj", "performans-sonucu", "toplam-kelime"},
            set(),
            "#container",
        ),
        (
            {"landingScreen", "startGameBtn", "gameScreen", "gameCard", "progressText", "scoreText", "correctFlash"},
            {"hero", "game-shell", "question-card"},
            ".hero",
        ),
        (
            {"sahne1", "basla", "sahne2", "oyunuyenile", "score", "sonuclar"},
            {"questionblock", "soru", "cevaplar"},
            "body.container",
        ),
        (
            {"sahne1", "sahne2", "app", "sonucsayfasi", "app1", "sonucsayfasi1", "gecisAnimasyon", "gecisAnimasyon2"},
            {"ortega", "result-card", "report-card"},
            "body",
        ),
    )

    def resolve(self, ids, classes=()):
        page = html_document(ids=ids, classes=classes)
        with patch.object(adapters, "fetch_html", return_value=(self.URL, page)):
            return adapters.IlkOkulNativeAdapter().resolve(self.URL)

    def test_extension_is_installed_for_production_import_path(self):
        self.assertEqual(
            adapters.IlkOkulNativeAdapter.resolve.__module__,
            adapter_extensions.__name__,
        )

    def test_all_known_families_resolve_to_exact_selector(self):
        for ids, classes, selector in self.FAMILIES:
            with self.subTest(selector=selector, ids=sorted(ids)):
                item = self.resolve(ids, classes)
                self.assertEqual(item.adapter, "ilk-okul-native")
                self.assertEqual(item.render_mode, "isolate")
                self.assertEqual(item.selector, selector)

    def test_each_family_rejects_a_required_token_near_miss(self):
        for ids, classes, selector in self.FAMILIES:
            with self.subTest(selector=selector, ids=sorted(ids)):
                reduced_ids = set(ids)
                reduced_ids.remove(sorted(reduced_ids)[0])
                with self.assertRaises(adapters.NotApplicable):
                    self.resolve(reduced_ids, classes)


class TestSaatiCharacterizationTests(unittest.TestCase):
    URL = "https://testsaati.com/quiz"

    def test_zombify_requires_explicit_quiz_fingerprint(self):
        positive = (
            "<html><head><title>Zombify</title></head><body>"
            '<div class="zf-quiz zf-trivia_quiz"></div>'
            "</body></html>"
        )
        with patch.object(adapters, "fetch_html", return_value=(self.URL, positive)):
            item = adapters.TestSaatiZombifyAdapter().resolve(self.URL)
        self.assertEqual(item.provider, "zombify")
        self.assertEqual(item.render_mode, "isolate")
        self.assertEqual(item.selector, ".zf-quiz")

        negative = '<html><body><div class="zf-quiz"></div></body></html>'
        with patch.object(adapters, "fetch_html", return_value=(self.URL, negative)):
            with self.assertRaises(adapters.NotApplicable):
                adapters.TestSaatiZombifyAdapter().resolve(self.URL)


class PersistenceCharacterizationTests(unittest.TestCase):
    def test_resolved_content_json_shape_and_tuple_restore_are_stable(self):
        item = adapters.ResolvedContent(
            kind="embed-collection",
            provider="wordwall",
            source_url="https://example.com/source",
            title="Fixture",
            content_url="https://wordwall.net/embed/one",
            content_urls=(
                "https://wordwall.net/embed/one",
                "https://wordwall.net/embed/two",
            ),
            adapter="generic-wordwall-page",
            render_mode="embed-collection",
        )
        payload = json.loads(ShortLinkStore._serialize(item))
        self.assertEqual(
            list(payload),
            [
                "kind",
                "provider",
                "source_url",
                "title",
                "content_url",
                "content_urls",
                "adapter",
                "render_mode",
                "selector",
            ],
        )
        restored = ShortLinkStore._deserialize(json.dumps(payload))
        self.assertEqual(restored, item)
        self.assertIsInstance(restored.content_urls, tuple)

    def test_current_payload_survives_real_store_round_trip(self):
        with tempfile.TemporaryDirectory() as directory:
            store = ShortLinkStore(
                Path(directory) / "links.sqlite3",
                ttl_seconds=60,
                code_length=6,
            )
            item = adapters.ResolvedContent(
                kind="native-exercise",
                provider="fixture",
                source_url="https://example.com/source",
                content_url="https://example.com/activity",
                adapter="fixture-native",
                render_mode="isolate",
                selector="#game",
            )
            code = store.save(item, now=100)
            self.assertEqual(store.get(code, now=120), item)


if __name__ == "__main__":
    unittest.main()
