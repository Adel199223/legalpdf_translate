from __future__ import annotations

from legalpdf_translate.resources_loader import get_resources_dir, resource_path


def test_resource_path_points_into_resources_dir() -> None:
    rel = "resources/system_instructions_enfr.txt"
    resolved = resource_path(rel)
    assert resolved.exists()
    assert resolved.parent == get_resources_dir()
