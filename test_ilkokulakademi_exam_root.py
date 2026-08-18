#!/usr/bin/env python3

from __future__ import annotations

import unittest
from unittest.mock import patch

import adapters


class IlkokulAkademiExamRootRegressionTests(unittest.TestCase):
    URL = "https://ilkokulakademi.com/2026/08/1-snf-matematik-deneme-snav-1.html"

    def test_exam_lifecycle_uses_wrapper_as_isolation_root(self):
        ids = (
            "exam-panel-wrapper",
            "start-screen",
            "active-game-container",
            "game-card",
            "question-text",
            "options-container",
            "result-screen",
            "final-score",
        )
        page = (
            "<!doctype html><html><head><title>Exam</title></head><body>"
            + "".join(f'<div id="{value}"></div>' for value in ids)
            + "</body></html>"
        )

        with patch.object(adapters, "fetch_html", return_value=(self.URL, page)):
            item = adapters.IlkokulAkademiNativeAdapter().resolve(self.URL)

        self.assertEqual(item.adapter, "ilkokulakademi-native")
        self.assertEqual(item.render_mode, "isolate")
        self.assertEqual(item.selector, "#exam-panel-wrapper")

    def test_legacy_active_game_family_keeps_existing_root(self):
        ids = (
            "active-game-container",
            "game-card",
            "question-text",
            "options-container",
            "result-screen",
            "final-score",
        )
        page = (
            "<!doctype html><html><head><title>Legacy</title></head><body>"
            + "".join(f'<div id="{value}"></div>' for value in ids)
            + "</body></html>"
        )

        with patch.object(adapters, "fetch_html", return_value=(self.URL, page)):
            item = adapters.IlkokulAkademiNativeAdapter().resolve(self.URL)

        self.assertEqual(item.selector, "#active-game-container")


if __name__ == "__main__":
    unittest.main()
