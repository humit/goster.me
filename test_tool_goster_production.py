#!/usr/bin/env python3

from __future__ import annotations

import subprocess
import tempfile
import unittest

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
PRODUCTION_MODULE = REPO_ROOT / "tools/gosterme/production.sh"


class GosterProductionCommandTests(unittest.TestCase):
    def test_http_probe_applies_bounded_curl_options(self):
        with tempfile.TemporaryDirectory() as tempdir:
            arguments = Path(tempdir) / "curl-arguments"
            script = r"""
set -euo pipefail
module="$1"
arguments="$2"
source "$module"
curl() {
    printf '%s\n' "$@" >"$arguments"
    printf '200'
}
probe_http_status https://example.test/
"""
            result = subprocess.run(
                ["bash", "-c", script, "bash", PRODUCTION_MODULE, arguments],
                check=True,
                capture_output=True,
                text=True,
            )
            curl_arguments = arguments.read_text().splitlines()

        self.assertEqual(result.stdout, "200")
        self.assertEqual(
            curl_arguments,
            [
                "--silent",
                "--show-error",
                "--connect-timeout",
                "2",
                "--max-time",
                "5",
                "--output",
                "/dev/null",
                "--write-out",
                "%{http_code}",
                "https://example.test/",
            ],
        )

    def test_prod_status_keeps_the_expected_readiness_targets(self):
        module = PRODUCTION_MODULE.read_text()

        self.assertIn("wait_for_http_status https://goster.me/ 200", module)
        self.assertIn(
            "wait_for_http_status https://s.goster.me/v/invalid 404",
            module,
        )
        self.assertIn("production HTTP readiness checks failed", module)


if __name__ == "__main__":
    unittest.main()
