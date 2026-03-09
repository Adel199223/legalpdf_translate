from __future__ import annotations

import pytest
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))


@pytest.fixture(autouse=True)
def _isolate_test_appdata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    appdata_root = tmp_path / "appdata"
    appdata_root.mkdir(parents=True, exist_ok=True)
    monkeypatch.setenv("APPDATA", str(appdata_root))
