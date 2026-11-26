from __future__ import annotations

import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import unittest


ROOT = Path(__file__).resolve().parents[2]
SKILLS_DIR = ROOT / ".agents" / "skills"
EXPECTED_SKILLS = (
    "legalpdf-validate",
    "legalpdf-browser-review",
    "legalpdf-word-review",
    "legalpdf-commit-publish",
)


def _parse_frontmatter(text: str) -> tuple[dict[str, str], str]:
    match = re.match(r"^---\r?\n(.*?)\r?\n---\r?\n(.*)$", text, flags=re.DOTALL)
    if not match:
        raise AssertionError("SKILL.md must start with valid YAML frontmatter delimited by ---")
    raw_yaml, body = match.group(1), match.group(2)
    fields: dict[str, str] = {}
    current_key: str | None = None
    current_lines: list[str] = []
    for line in raw_yaml.splitlines():
        key_match = re.match(r"^([A-Za-z0-9_-]+):\s*(.*)$", line)
        if key_match and not line.startswith((" ", "\t")):
            if current_key is not None:
                fields[current_key] = " ".join(part.strip() for part in current_lines if part.strip()).strip()
            current_key = key_match.group(1)
            value = key_match.group(2).strip()
            current_lines = [] if value in (">", ">-", "|", "|-") else [value]
        elif current_key is not None:
            current_lines.append(line.strip())
    if current_key is not None:
        fields[current_key] = " ".join(part.strip() for part in current_lines if part.strip()).strip()
    return fields, body


class AntigravityWorkspaceConfigTests(unittest.TestCase):
    def test_agents_md_rule_constraints_and_no_duplicate_gemini_md(self) -> None:
        agents_path = ROOT / "AGENTS.md"
        self.assertTrue(agents_path.is_file(), "Root AGENTS.md is required.")
        self.assertFalse(
            (ROOT / "GEMINI.md").exists(),
            "Root GEMINI.md must not duplicate AGENTS.md (Antigravity auto-loads AGENTS.md).",
        )
        raw_bytes = agents_path.read_bytes()
        self.assertLess(
            len(raw_bytes),
            24_000,
            f"AGENTS.md exceeds Antigravity's 24,000-byte per-file rule cap ({len(raw_bytes)} bytes).",
        )
        text = raw_bytes.decode("utf-8")
        self.assertIn(".agents/skills/", text)
        self.assertIn("`gmail` plugin", text)
        self.assertIn("`browser` subagent", text)
        self.assertIn("windows-desktop-control", text)

    def test_workspace_skills_frontmatter_size_and_path_references(self) -> None:
        self.assertTrue(SKILLS_DIR.is_dir(), ".agents/skills/ directory must exist.")
        actual_dirs = sorted(p.name for p in SKILLS_DIR.iterdir() if p.is_dir())
        self.assertEqual(actual_dirs, sorted(EXPECTED_SKILLS))

        for skill_name in EXPECTED_SKILLS:
            skill_file = SKILLS_DIR / skill_name / "SKILL.md"
            self.assertTrue(skill_file.is_file(), f"Missing {skill_file}")
            raw_bytes = skill_file.read_bytes()
            self.assertLess(
                len(raw_bytes),
                8192,
                f"{skill_file} should stay concise (< 8 KB), got {len(raw_bytes)} bytes.",
            )
            text = raw_bytes.decode("utf-8")
            fields, body = _parse_frontmatter(text)
            self.assertEqual(fields.get("name"), skill_name)
            self.assertTrue(fields.get("description"), f"Empty description in {skill_file}")
            self.assertNotIn(".codex/browser/", text.replace("\\", "/"))
            self.assertTrue(body.strip())

            # Verify repo-relative doc/tooling/script backtick paths exist on disk.
            for token in re.findall(r"`([^`\r\n]+)`", body):
                candidate = token.strip()
                if any(ch in candidate for ch in ("*", "<", ">", " ", "|", ":")):
                    continue
                if candidate.startswith(("docs/assistant/", "tooling/", "scripts/")) or candidate in (
                    "AGENTS.md",
                    "agent.md",
                ):
                    self.assertTrue(
                        (ROOT / candidate).exists(),
                        f"Referenced path `{candidate}` in {skill_file} does not exist.",
                    )

    def test_validate_dev_docs_trigger_covers_antigravity_files(self) -> None:
        ps_exe = shutil.which("powershell") or shutil.which("pwsh")
        if os.name != "nt" or not ps_exe:
            self.skipTest("Windows PowerShell behavioral trigger check requires Windows.")

        script_path = ROOT / "scripts" / "validate_dev.ps1"
        ps_command = f"""
$ErrorActionPreference = 'Stop'
$tokens = $null
$errors = $null
$ast = [System.Management.Automation.Language.Parser]::ParseFile('{str(script_path).replace("'", "''")}', [ref]$tokens, [ref]$errors)
if ($errors.Count -gt 0) {{ throw "Parse errors in validate_dev.ps1" }}
$fn = $ast.Find({{ param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst] -and $node.Name -eq 'Test-DocsValidationTriggered' }}, $true)
if ($null -eq $fn) {{ throw "Test-DocsValidationTriggered not found" }}
Invoke-Expression $fn.Extent.Text
$cases = @(
  'AGENTS.md',
  'agent.md',
  '.agents/skills/legalpdf-validate/SKILL.md',
  'docs/assistant/LOCAL_CAPABILITIES.md',
  'README.md',
  'APP_KNOWLEDGE.md',
  'src/legalpdf_translate/cli.py',
  'tests/test_cli_flags.py'
)
foreach ($c in $cases) {{
  $res = Test-DocsValidationTriggered -Paths @($c)
  Write-Output "$c=$res"
}}
"""
        completed = subprocess.run(
            [ps_exe, "-NoProfile", "-ExecutionPolicy", "Bypass", "-Command", ps_command],
            check=True,
            capture_output=True,
            text=True,
        )
        results = dict(
            line.split("=", 1)
            for line in completed.stdout.strip().splitlines()
            if "=" in line
        )
        self.assertEqual(results.get("AGENTS.md"), "True")
        self.assertEqual(results.get("agent.md"), "True")
        self.assertEqual(results.get(".agents/skills/legalpdf-validate/SKILL.md"), "True")
        self.assertEqual(results.get("docs/assistant/LOCAL_CAPABILITIES.md"), "True")
        self.assertEqual(results.get("README.md"), "True")
        self.assertEqual(results.get("APP_KNOWLEDGE.md"), "True")
        self.assertEqual(results.get("src/legalpdf_translate/cli.py"), "False")
        self.assertEqual(results.get("tests/test_cli_flags.py"), "False")

    def test_vscode_settings_excludes_noisy_dirs(self) -> None:
        settings_path = ROOT / ".vscode" / "settings.json"
        self.assertTrue(settings_path.is_file(), ".vscode/settings.json is required.")
        data = json.loads(settings_path.read_text(encoding="utf-8"))
        watcher = data.get("files.watcherExclude", {})
        search = data.get("search.exclude", {})

        for pattern in ("**/.venv311/**", "**/.playwright-cli/**", "**/.playwright-mcp/**", "**/tmp/**"):
            self.assertIs(watcher.get(pattern), True, f"files.watcherExclude missing {pattern}")
            self.assertIs(search.get(pattern), True, f"search.exclude missing {pattern}")

        for pattern in ("**/docs/assistant/history/**", "**/docs/assistant/exec_plans/completed/**"):
            self.assertIs(search.get(pattern), True, f"search.exclude missing {pattern}")


if __name__ == "__main__":
    unittest.main()
