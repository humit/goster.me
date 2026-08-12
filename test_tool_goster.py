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
    def test_analytics_command_runs_report_with_forwarded_arguments(self):
        repo_root = Path(__file__).resolve().parent

        with tempfile.TemporaryDirectory() as tempdir:
            database = Path(tempdir) / "goster.sqlite3"
            store = AnalyticsStore(database)
            store.record("landing_view", now=int(time.time()))

            env = os.environ.copy()
            env.update(
                {
                    "GOSTER_APP_ROOT": str(repo_root),
                    "GOSTER_APP_USER": os.environ.get("USER", "root"),
                    "GOSTER_DATABASE": str(database),
                    "GOSTER_PYTHON": sys.executable,
                }
            )
            result = subprocess.run(
                [str(repo_root / "tools/goster"), "analytics", "--since-hours", "1"],
                cwd=repo_root,
                env=env,
                check=True,
                capture_output=True,
                text=True,
            )

        self.assertIn("goster.me analytics since_hours=1 campaign=all", result.stdout)
        self.assertIn("landing_view", result.stdout)
        self.assertRegex(result.stdout, r"landing_view\s+1")


if __name__ == "__main__":
    unittest.main()
