from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter

PROJECT_ROOT = Path(__file__).resolve().parents[1]
ICONS_DIR = PROJECT_ROOT / "resources" / "icons"
PNG_PATH = ICONS_DIR / "LegalPDFTranslate.png"
ICO_PATH = ICONS_DIR / "LegalPDFTranslate.ico"

MASTER_SIZE = 1024
CORNER_RADIUS = 220
ICO_SIZES = [16, 24, 32, 48, 64, 128, 256]


def _rounded_mask(size: int, radius: int) -> Image.Image:
    mask = Image.new("L", (size, size), 0)
    draw = ImageDraw.Draw(mask)
    draw.rounded_rectangle((0, 0, size - 1, size - 1), radius=radius, fill=255)
    return mask


def _add_glow(
    image: Image.Image,
    center_x: int,
    center_y: int,
    radius: int,
    color: tuple[int, int, int],
    alpha: int,
) -> None:
    glow = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(glow)
    box = (
        center_x - radius,
        center_y - radius,
        center_x + radius,
        center_y + radius,
    )
    draw.ellipse(box, fill=(*color, alpha))
    glow = glow.filter(ImageFilter.GaussianBlur(radius=max(2, radius // 3)))
    image.alpha_composite(glow)


def _draw_background() -> Image.Image:
    canvas = Image.new("RGBA", (MASTER_SIZE, MASTER_SIZE), (0, 0, 0, 0))
    gradient = Image.new("RGBA", (MASTER_SIZE, MASTER_SIZE), (0, 0, 0, 0))
    grad = ImageDraw.Draw(gradient)
    for y in range(MASTER_SIZE):
        t = y / (MASTER_SIZE - 1)
        r = int(3 + 9 * t)
        g = int(13 + 20 * t)
        b = int(34 + 30 * t)
        grad.line((0, y, MASTER_SIZE, y), fill=(r, g, b, 255))

    mask = _rounded_mask(MASTER_SIZE, CORNER_RADIUS)
    base = Image.composite(gradient, canvas, mask)
    canvas.alpha_composite(base)

    _add_glow(canvas, 265, 265, 250, (18, 178, 230), 135)
    _add_glow(canvas, 760, 780, 270, (21, 224, 255), 110)
    _add_glow(canvas, 820, 280, 170, (20, 190, 230), 78)

    border = ImageDraw.Draw(canvas)
    border.rounded_rectangle(
        (18, 18, MASTER_SIZE - 19, MASTER_SIZE - 19),
        radius=CORNER_RADIUS,
        outline=(73, 210, 255, 170),
        width=8,
    )
    return canvas


def _draw_mark(canvas: Image.Image) -> None:
    draw = ImageDraw.Draw(canvas)

    # Document panel.
    doc = (210, 170, 620, 790)
    draw.rounded_rectangle(
        doc,
        radius=48,
        fill=(224, 243, 255, 236),
        outline=(134, 223, 255, 245),
        width=8,
    )

    fold = [
        (doc[2] - 130, doc[1]),
        (doc[2], doc[1] + 132),
        (doc[2], doc[1]),
    ]
    draw.polygon(fold, fill=(174, 226, 252, 238))
    draw.line(
        ((doc[2] - 130, doc[1]), (doc[2] - 130, doc[1] + 130), (doc[2], doc[1] + 130)),
        fill=(136, 208, 245, 230),
        width=7,
    )

    # "A" glyph on the document.
    stroke = (11, 39, 76, 220)
    draw.line((315, 620, 420, 320), fill=stroke, width=28, joint="curve")
    draw.line((420, 320, 525, 620), fill=stroke, width=28, joint="curve")
    draw.line((358, 500, 482, 500), fill=stroke, width=24)

    # Translation arrows.
    neon = (40, 234, 255, 250)
    draw.line(
        ((430, 450), (620, 450), (770, 340)),
        fill=neon,
        width=34,
        joint="curve",
    )
    draw.polygon(
        ((772, 304), (850, 340), (772, 376)),
        fill=neon,
    )

    draw.line(
        ((815, 600), (625, 600), (472, 712)),
        fill=neon,
        width=34,
        joint="curve",
    )
    draw.polygon(
        ((470, 676), (392, 712), (470, 748)),
        fill=neon,
    )

    _add_glow(canvas, 652, 452, 130, (35, 232, 255), 75)
    _add_glow(canvas, 628, 603, 130, (35, 232, 255), 65)

    # Minimal "文"-inspired strokes to suggest multilingual translation.
    ideograph = (222, 248, 255, 242)
    draw.line((690, 448, 862, 448), fill=ideograph, width=22)
    draw.line((776, 448, 728, 536), fill=ideograph, width=22)
    draw.line((776, 448, 824, 536), fill=ideograph, width=22)
    draw.line((690, 574, 862, 574), fill=ideograph, width=22)
    draw.line((776, 574, 776, 716), fill=ideograph, width=22)


def _write_outputs(image: Image.Image) -> None:
    ICONS_DIR.mkdir(parents=True, exist_ok=True)
    image.save(PNG_PATH, format="PNG")

    sizes = [(size, size) for size in ICO_SIZES]
    image.save(ICO_PATH, format="ICO", sizes=sizes)


def main() -> None:
    icon = _draw_background()
    _draw_mark(icon)
    _write_outputs(icon)
    print(f"Generated: {PNG_PATH}")
    print(f"Generated: {ICO_PATH}")


if __name__ == "__main__":
    main()
