from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
import unittest

ROOT = Path(__file__).resolve().parents[2]
TOOLING = ROOT / "tooling"
REGISTRY = ROOT / "docs/assistant/templates/BOOTSTRAP_ARCHETYPE_REGISTRY.json"
PROFILE = ROOT / "docs/assistant/templates/examples/DESKTOP_PYTHON_QT.profile.json"

sys.path.insert(0, str(TOOLING))

from harness_profile_lib import load_json, make_state, resolve_plan, validate_profile  # noqa: E402
from harness_profile_lib import resolve_sync_targets  # noqa: E402


class HarnessToolTests(unittest.TestCase):
    def test_profile_validates(self) -> None:
        profile = load_json(PROFILE)
        registry = load_json(REGISTRY)
        self.assertEqual(validate_profile(profile, registry), [])

    def test_resolution_includes_desktop_support(self) -> None:
        profile = load_json(PROFILE)
        registry = load_json(REGISTRY)
        plan = resolve_plan(profile, registry)
        self.assertIn("desktop_launcher", plan["modules"])
        self.assertIn("openai_docs_mcp", plan["modules"])
        self.assertIn("docs/assistant/CODEX_ENVIRONMENT.md", plan["outputs"])

    def test_state_generation(self) -> None:
        profile = load_json(PROFILE)
        registry = load_json(REGISTRY)
        state = make_state(profile, registry)
        self.assertEqual(state["schema_version"], 1)
        self.assertEqual(state["resolved"]["archetype"], "desktop_python_qt")
        self.assertTrue(state["profile_fingerprint"])

    def test_sync_targets_apply_repo_output_mappings(self) -> None:
        profile = load_json(PROFILE)
        registry = load_json(REGISTRY)
        template_map = load_json(ROOT / "docs/assistant/templates/BOOTSTRAP_TEMPLATE_MAP.json")
        plan = resolve_plan(profile, registry)
        sync_resolution = resolve_sync_targets(plan, template_map)
        self.assertIn("README.md", sync_resolution["sync_targets"])
        self.assertIn(
            "docs/assistant/SESSION_RESUME.md",
            sync_resolution["sync_targets"],
        )
        self.assertEqual(
            sync_resolution["mapped_outputs"]["docs/assistant/START_HERE.md"],
            ["README.md"],
        )

    def test_cli_preview_json(self) -> None:
        result = subprocess.run(
            [
                sys.executable,
                str(TOOLING / "preview_harness_sync.py"),
                "--profile",
                str(PROFILE),
                "--registry",
                str(REGISTRY),
                "--json",
            ],
            check=True,
            capture_output=True,
            text=True,
        )
        data = json.loads(result.stdout)
        self.assertEqual(data["archetype"], "desktop_python_qt")
        self.assertIn("sync_targets", data)
        self.assertEqual(data["missing_sync_targets"], [])


if __name__ == "__main__":
    unittest.main()
