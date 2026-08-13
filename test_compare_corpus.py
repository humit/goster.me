#!/usr/bin/env python3

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


SCRIPT = Path(__file__).with_name("compare-corpus")


def record(status: str, **values) -> dict:
    return {
        "status": status,
        "provider": None,
        "adapter": None,
        "kind": None,
        "render_mode": None,
        "selector": None,
        "content_url": None,
        **values,
    }


class CompareCorpusTests(unittest.TestCase):
    def run_compare(self, baseline, current, *args):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            paths = (root / "baseline.json", root / "current.json")
            for path, records in zip(paths, (baseline, current)):
                path.write_text(
                    json.dumps({"version": 1, "urls": records}),
                    encoding="utf-8",
                )
            return subprocess.run(
                [sys.executable, str(SCRIPT), *args, *map(str, paths)],
                check=False,
                capture_output=True,
                text=True,
            )

    def test_reports_aggregate_improvements_without_urls(self):
        private_url = "https://example.com/private-activity"
        completed = record(
            "resolved",
            provider="example",
            adapter="example-native",
            kind="native-exercise",
            render_mode="isolate",
            selector="#game",
            content_url=private_url,
        )
        result = self.run_compare(
            {private_url: record("known-unresolved")},
            {
                private_url: completed,
                "https://new.example/": record("unsupported"),
            },
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        report = json.loads(result.stdout)
        self.assertEqual(report["improvements"], 1)
        self.assertEqual(report["regressions"], 0)
        self.assertEqual(report["added_urls"], 1)
        self.assertEqual(
            report["transitions"],
            {"known-unresolved -> resolved": 1},
        )
        self.assertEqual(
            report["dimensions"]["adapter"]["delta"],
            {"example-native": 1},
        )
        self.assertNotIn(private_url, result.stdout)

    def test_counts_changed_resolved_output(self):
        url = "https://example.com/activity"
        before = record(
            "resolved",
            adapter="example-native",
            render_mode="isolate",
            selector="#old",
            content_url=url,
        )
        result = self.run_compare(
            {url: before},
            {url: {**before, "selector": "#new"}},
        )

        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(
            json.loads(result.stdout)["changed_resolved_output"],
            1,
        )

    def test_fail_on_regression_returns_one(self):
        url = "https://example.com/activity"
        result = self.run_compare(
            {url: record("resolved", adapter="example-native")},
            {url: record("known-unresolved")},
            "--fail-on-regression",
        )

        self.assertEqual(result.returncode, 1)
        self.assertEqual(json.loads(result.stdout)["regressions"], 1)

    def test_rejects_invalid_cache(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            baseline = root / "baseline.json"
            current = root / "current.json"
            baseline.write_text('{"version": 2, "urls": {}}', encoding="utf-8")
            current.write_text('{"version": 1, "urls": {}}', encoding="utf-8")
            result = subprocess.run(
                [sys.executable, str(SCRIPT), str(baseline), str(current)],
                check=False,
                capture_output=True,
                text=True,
            )

        self.assertEqual(result.returncode, 2)
        self.assertIn("unsupported cache version", result.stderr)


if __name__ == "__main__":
    unittest.main()
