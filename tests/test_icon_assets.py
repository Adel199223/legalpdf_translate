from __future__ import annotations

from pathlib import Path

from PIL import Image

PNG_PATH = Path("resources/icons/LegalPDFTranslate.png")
ICO_PATH = Path("resources/icons/LegalPDFTranslate.ico")
REQUIRED_SIZES = {16, 24, 32, 48, 64, 128, 256}


def _ico_sizes(path: Path) -> set[int]:
    sizes: set[int] = set()
    with Image.open(path) as icon:
        raw_sizes = icon.info.get("sizes")
        if raw_sizes:
            sizes.update(width for width, height in raw_sizes if width == height)

        while True:
            sizes.add(icon.size[0])
            try:
                icon.seek(icon.tell() + 1)
            except EOFError:
                break
    return sizes


def test_icon_assets_exist() -> None:
    assert PNG_PATH.exists()
    assert ICO_PATH.exists()


def test_icon_png_is_high_resolution() -> None:
    with Image.open(PNG_PATH) as image:
        assert image.width >= 256
        assert image.height >= 256


def test_icon_ico_contains_required_sizes() -> None:
    sizes = _ico_sizes(ICO_PATH)
    assert REQUIRED_SIZES.issubset(sizes)
