import unittest

from onboarding_demo import DEMO_ROUTE, render_activity_demo


class OnboardingDemoTests(unittest.TestCase):
    def setUp(self):
        self.html = render_activity_demo()

    def test_demo_route_is_explicit_and_non_root(self):
        self.assertEqual(DEMO_ROUTE, "/demo/activity")

    def test_demo_explains_before_after_transformation(self):
        self.assertIn("İçerik aynı. Etrafı değişiyor.", self.html)
        self.assertIn("Etkinlik aynı kalırken", self.html)
        self.assertIn("kaynak sayfanın geri kalanı gösterilmiyor", self.html)

    def test_demo_exposes_repeatable_source_and_clean_toggle(self):
        self.assertIn('data-demo-mode="source"', self.html)
        self.assertIn('data-demo-mode="clean"', self.html)
        self.assertIn('aria-pressed="true">Göster</button>', self.html)
        self.assertIn('aria-pressed="false">goster.me</button>', self.html)
        self.assertIn("function setMode(mode)", self.html)

    def test_demo_keeps_activity_constant_between_modes(self):
        self.assertEqual(self.html.count('class="activity"'), 1)
        self.assertIn("8 + 7 kaç eder?", self.html)
        self.assertIn('[data-mode="clean"] .source-header', self.html)
        self.assertIn('[data-mode="clean"] .source-side', self.html)

    def test_demo_is_fully_local(self):
        self.assertNotIn("https://", self.html)
        self.assertNotIn("http://", self.html)
        self.assertNotIn("<iframe", self.html)
        self.assertNotIn("<img", self.html)

    def test_demo_has_accessible_controls_and_reduced_motion_fallback(self):
        self.assertIn('role="group" aria-label="Demo görünümü"', self.html)
        self.assertIn('aria-live="polite"', self.html)
        self.assertIn("prefers-reduced-motion: reduce", self.html)

    def test_demo_returns_to_primary_task(self):
        self.assertIn('href="/">← Kendi bağlantını dene</a>', self.html)


if __name__ == "__main__":
    unittest.main()
