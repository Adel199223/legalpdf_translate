from __future__ import annotations

import ast
from pathlib import Path

STARTUP_MODULES = [
    Path("src/legalpdf_translate/qt_main.py"),
    Path("src/legalpdf_translate/qt_app.py"),
    Path("src/legalpdf_translate/qt_gui/app_window.py"),
    Path("src/legalpdf_translate/qt_gui/dialogs.py"),
    Path("src/legalpdf_translate/qt_gui/worker.py"),
]


def _find_relative_imports(module_path: Path) -> list[tuple[int, str]]:
    tree = ast.parse(module_path.read_text(encoding="utf-8-sig"), filename=str(module_path))
    findings: list[tuple[int, str]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom) and node.level > 0:
            module = "." * node.level + (node.module or "")
            findings.append((node.lineno, module))
    return findings


def test_qt_startup_modules_use_absolute_imports() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    for relative_path in STARTUP_MODULES:
        module_path = repo_root / relative_path
        findings = _find_relative_imports(module_path)
        assert not findings, (
            f"{relative_path} contains relative imports: "
            + ", ".join(f"line {line}: {module}" for line, module in findings)
        )
