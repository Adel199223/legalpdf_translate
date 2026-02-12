from __future__ import annotations

from legalpdf_translate.resources_loader import resource_path as loader_resource_path
from legalpdf_translate.ui_assets import resource_path as ui_resource_path


def test_shared_resource_path_helper_is_consistent() -> None:
    rel = "resources/system_instructions_enfr.txt"
    assert loader_resource_path(rel) == ui_resource_path(rel)
