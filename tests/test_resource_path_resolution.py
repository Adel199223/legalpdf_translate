from __future__ import annotations

from legalpdf_translate.resources_loader import get_resources_dir, resource_path


def test_resource_path_points_into_resources_dir() -> None:
    resources_dir = get_resources_dir()
    for rel in (
        "resources/system_instructions_en.txt",
        "resources/system_instructions_fr.txt",
        "resources/system_instructions_ar.txt",
    ):
        resolved = resource_path(rel)
        assert resolved.exists()
        assert resolved.parent == resources_dir
