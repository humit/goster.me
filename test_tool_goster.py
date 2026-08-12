#!/usr/bin/env python3

from __future__ import annotations

import os
import subprocess
import sys
import tempfile
import time
import unittest

from pathlib import Path

from analytics import AnalyticsStore


class GosterToolTests(unittest.TestCase):
    def test_prod_status_uses_bounded_http_readiness_checks(self):
        tool = (Path(__file__).resolve().parent / "tools/goster").read_text()

        self.assertIn("wait_for_http_status()", tool)
        self.assertIn("--connect-timeout 2", tool)
        self.assertIn("--max-time 5", tool)
        self.assertIn("wait_for_http_status https://goster.me/ 200", tool)
        self.assertIn(
            "wait_for_http_status https://s.goster.me/v/invalid 404",
            tool,
        )
        self.assertIn("production HTTP readiness checks failed", tool)

    def test_analytics_command_runs_report_with_forwarded_arguments(self):
        repo_root = Path(__file__).resolve().parent

        with tempfile.TemporaryDirectory() as tempdir:
            database = Path(tempdir) / "goster.sqlite3"
            key = "analytics-test-key-0123456789abcdef"
            store = AnalyticsStore(database, key=key)
            store.record(
                "landing_view", now=int(time.time()), visitor_ip="203.0.113.10"
            )
            store.record(
                "landing_view", now=int(time.time()), visitor_ip="198.51.100.20"
            )

            env = os.environ.copy()
            env.update(
                {
                    "GOSTER_APP_ROOT": str(repo_root),
                    "GOSTER_APP_USER": os.environ.get("USER", "root"),
                    "GOSTER_DATABASE": str(database),
                    "GOSTER_PYTHON": sys.executable,
                    "GOSTER_ANALYTICS_KEY": key,
                    "SSH_CONNECTION": "203.0.113.10 54321 192.0.2.10 22",
                }
            )
            result = subprocess.run(
                [
                    str(repo_root / "tools/goster"),
                    "analytics",
                    "--since-hours",
                    "1",
                    "--exclude-current-ssh-client",
                ],
                cwd=repo_root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertIn("goster.me analytics since_hours=1 campaign=all", result.stdout)
        self.assertIn("excluded_events=1", result.stdout)
        self.assertIn("landing_view", result.stdout)
        self.assertRegex(result.stdout, r"landing_view\s+1")


if __name__ == "__main__":
    unittest.main()
