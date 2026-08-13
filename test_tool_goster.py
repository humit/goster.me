#!/usr/bin/env python3

from __future__ import annotations

import re
import subprocess
import unittest

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
TOOL = REPO_ROOT / "tools/goster"
MODULES = (
    REPO_ROOT / "tools/gosterme/common.sh",
    REPO_ROOT / "tools/gosterme/staging.sh",
    REPO_ROOT / "tools/gosterme/production.sh",
    REPO_ROOT / "tools/gosterme/application.sh",
)


class GosterToolLayoutTests(unittest.TestCase):
    def test_entrypoint_is_only_a_compatible_dispatcher(self):
        entrypoint = TOOL.read_text()

        for module in MODULES:
            relative = module.relative_to(REPO_ROOT / "tools")
            self.assertIn(f'source "${{TOOL_DIR}}/{relative}"', entrypoint)
            self.assertTrue(module.is_file())

        self.assertIsNone(re.search(r"(?m)^cmd_[a-z_]+\(\)", entrypoint))

    def test_all_shell_components_parse(self):
        for path in (TOOL, *MODULES):
            with self.subTest(path=path.relative_to(REPO_ROOT)):
                subprocess.run(["bash", "-n", path], check=True)

    def test_help_preserves_the_public_command_surface(self):
        result = subprocess.run(
            [TOOL, "help"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )

        for command in (
            "stage <ref>",
            "stage-status",
            "stage-test",
            "prod-preflight",
            "prod-status",
            "analytics",
            "feedback",
            "unsupported",
        ):
            self.assertIn(command, result.stdout)


if __name__ == "__main__":
    unittest.main()
