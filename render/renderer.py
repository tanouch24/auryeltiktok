"""
renderer.py — Pillow-based image generation for Auryel TikTok carousels.
Layouts: oracle (ornate), minimal (clean), mystique (atmospheric).
"""

import random
import math
import logging
from pathlib import Path
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

WIDTH  = 1080
HEIGHT = 1920

VOID          = (10, 10, 20)
VIOLET        = (45, 18, 96)
ACCENT_VIOLET = (107, 33, 168)
GOLD          = (212, 175, 55)
GOLD_BRIGHT   = (240, 208, 96)
WHITE         = (255, 255, 255)
CREAM         = (253, 246, 227)

# Radial gradient parameters per layout
_LAYOUT_GRADIENT = {
    "oracle":  {"center": (45, 18, 96),  "outer": (10, 10, 20)},
    "minimal": {"center": (18, 8,  38),  "outer": (8,  6,  14)},
    "mystique":{"center": (70, 22, 118), "outer": (6,  3,  16)},
}

# Star density per layout — reduced 35% vs original for cleaner depth
_LAYOUT_STARS = {
    "oracle":  (32, 42),
    "minimal": (6,  11),
    "mystique":(18, 26),
}

# Focal element positions per layout (cx, cy) — soft moon/halo in upper breathing zone
_FOCAL_POSITIONS = {
    "oracle":  (780, 340),   # warm gold glow, upper right
    "minimal": (740, 290),   # cool white glow, upper right
    "mystique":(310, 360),   # violet-white glow, upper left
}

# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
FONTS_DIR  = ASSETS_DIR / "fonts"
FONTS_DIR.mkdir(parents=True, exist_ok=True)

FONT_URLS = {
    "Cinzel-Regular.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/cinzel/Cinzel%5Bwght%5D.ttf",
    "Cinzel-Bold.ttf":    "https://raw.githubusercontent.com/google/fonts/main/ofl/cinzel/Cinzel%5Bwght%5D.ttf",
    "Lora-Regular.ttf":   "https://raw.githubusercontent.com/google/fonts/main/ofl/lora/Lora%5Bwght%5D.ttf",
    "Lora-Italic.ttf":    "https://raw.githubusercontent.com/google/fonts/main/ofl/lora/Lora-Italic%5Bwght%5D.ttf",
}


def _download_font(name: str) -> Optional[Path]:
    dest = FONTS_DIR / name
    if dest.exists():
        return dest
    url = FONT_URLS.get(name)
    if not url:
        return None
    try:
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        dest.write_bytes(r.content)
        logger.info(f"[fonts] Saved {name} ({len(r.content)//1024} KB)")
        return dest
    except Exception as exc:
        logger.warning(f"[fonts] Failed to download {name}: {exc}")
    return None


def _load_font(family: str, style: str, size: int) -> ImageFont.FreeTypeFont:
    name_map = {
        ("Cinzel", "Regular"): "Cinzel-Regular.ttf",
        ("Cinzel", "Bold"):    "Cinzel-Bold.ttf",
        ("Lora",   "Regular"): "Lora-Regular.ttf",
        ("Lora",   "Bold"):    "Lora-Regular.ttf",
        ("Lora",   "Italic"):  "Lora-Italic.ttf",
    }
    if style == "Bold" and family == "Lora":
        logger.warning("[fonts] Lora Bold unavailable, using Regular")
    filename = name_map.get((family, style), name_map.get((family, "Regular")))
    if filename:
        path = _download_font(filename)
        if path and path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except Exception as exc:
                logger.warning(f"[fonts] truetype load failed for {path}: {exc}")
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _draw_radial_gradient(img: Image.Image, layout: str = "oracle") -> None:
    colors = _LAYOUT_GRADIENT.get(layout, _LAYOUT_GRADIENT["oracle"])
    center = colors["center"]
    outer  = colors["outer"]
    draw   = ImageDraw.Draw(img)
    steps  = 120
    cx, cy = WIDTH // 2, HEIGHT // 2
    max_rx = int(math.sqrt(cx**2 + cy**2)) + 20

    for i in range(steps):
        t  = i / (steps - 1)
        r  = int(outer[0] + (center[0] - outer[0]) * t)
        g  = int(outer[1] + (center[1] - outer[1]) * t)
        b  = int(outer[2] + (center[2] - outer[2]) * t)
        rx = int(max_rx * (1 - t * 0.65))
        ry = int(max_rx * (1 - t * 0.55))
        draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=(r, g, b))


def _draw_stars(img: Image.Image, seed: int = 42, count: int = 40, layout: str = "oracle") -> None:
    """Two-tier stars: 70% small/distant (dim), 30% large/bright (near) — creates depth."""
    draw = ImageDraw.Draw(img)
    rng  = random.Random(seed)

    for _ in range(count):
        x = rng.randint(20, WIDTH - 20)
        y = rng.randint(20, HEIGHT - 20)
        is_distant = rng.random() < 0.70

        if layout == "minimal":
            size  = 1 if is_distant else rng.randint(2, 3)
            shape = "dot"
            alpha = rng.randint(40, 80) if is_distant else rng.randint(90, 140)
        elif layout == "mystique":
            size  = 1 if is_distant else rng.randint(2, 4)
            shape = "dot" if is_distant else rng.choice(["dot", "diamond"])
            alpha = rng.randint(45, 90) if is_distant else rng.randint(130, 195)
        else:  # oracle
            size  = rng.randint(1, 2) if is_distant else rng.randint(3, 5)
            shape = "dot" if is_distant else rng.choice(["dot", "diamond"])
            alpha = rng.randint(50, 95) if is_distant else rng.randint(155, 220)

        color = (GOLD[0], GOLD[1], GOLD[2], alpha)
        if shape == "dot":
            draw.ellipse([x - size, y - size, x + size, y + size], fill=color)
        else:
            draw.polygon(
                [(x, y - size * 2), (x + size, y), (x, y + size * 2), (x - size, y)],
                fill=color,
            )


def _draw_border_frame(img: Image.Image, inset: int = 22, thickness: int = 2) -> None:
    """Oracle: thin semi-transparent gold rectangular border."""
    draw = ImageDraw.Draw(img)
    x0, y0 = inset, inset
    x1, y1 = WIDTH - inset, HEIGHT - inset
    c = (GOLD[0], GOLD[1], GOLD[2], 160)
    draw.rectangle([x0, y0, x1, y0 + thickness], fill=c)
    draw.rectangle([x0, y1 - thickness, x1, y1], fill=c)
    draw.rectangle([x0, y0, x0 + thickness, y1], fill=c)
    draw.rectangle([x1 - thickness, y0, x1, y1], fill=c)


def _draw_center_glow(img: Image.Image) -> None:
    """Mystique: layered violet glow at image center."""
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)
    cx, cy  = WIDTH // 2, HEIGHT // 2
    for i in range(6, 0, -1):
        alpha = 18 * i // 6
        rx    = 320 * i // 6
        ry    = 260 * i // 6
        c     = (ACCENT_VIOLET[0], ACCENT_VIOLET[1], ACCENT_VIOLET[2], alpha)
        draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry], fill=c)
    img.alpha_composite(overlay)


def _draw_focal_element(img: Image.Image, layout: str = "oracle") -> None:
    """Single atmospheric focal element (soft moon/halo) in the upper breathing zone."""
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)
    cx, cy  = _FOCAL_POSITIONS.get(layout, (780, 340))

    if layout == "minimal":
        layers = [(90, 6), (58, 11), (30, 16), (12, 20)]
        base   = (230, 230, 255)
    elif layout == "mystique":
        layers = [(110, 5), (72, 10), (38, 16), (15, 22)]
        base   = (200, 180, 255)
    else:  # oracle — warm gold-white moon
        layers = [(100, 7), (65, 13), (33, 20), (13, 26)]
        base   = (245, 215, 130)

    for radius, alpha in layers:
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                     fill=(*base, alpha))
    img.alpha_composite(overlay)


def _make_base(seed: int = 42, star_count: Optional[int] = None, layout: str = "oracle") -> Image.Image:
    img = Image.new("RGBA", (WIDTH, HEIGHT), VOID)
    _draw_radial_gradient(img, layout=layout)
    _draw_focal_element(img, layout=layout)   # behind stars for depth
    if star_count is None:
        lo, hi = _LAYOUT_STARS.get(layout, (30, 50))
        count = random.Random(seed).randint(lo, hi)
    else:
        count = star_count
    _draw_stars(img, seed=seed, count=count, layout=layout)
    if layout == "oracle":
        _draw_border_frame(img)
    elif layout == "mystique":
        _draw_center_glow(img)
    return img


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    words   = text.split()
    lines   = []
    current = []
    for word in words:
        test = " ".join(current + [word])
        bbox = draw.textbbox((0, 0), test, font=font)
        if bbox[2] - bbox[0] <= max_width:
            current.append(word)
        else:
            if current:
                lines.append(" ".join(current))
                current = [word]
            else:
                lines.append(word)
    if current:
        lines.append(" ".join(current))
    return lines


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    color: tuple,
    y: int,
    max_width: int = WIDTH - 80,
    line_spacing: int = 20,
) -> int:
    """Draw word-wrapped centered text. Returns y after last line."""
    lines = _wrap_text(text, font, max_width, draw)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        x = (WIDTH - (bbox[2] - bbox[0])) // 2
        draw.text((x, y), line, font=font, fill=color)
        y += (bbox[3] - bbox[1]) + line_spacing
    return y


def _draw_gold_line(draw: ImageDraw.ImageDraw, y: int, length: int = 200, thickness: int = 4) -> None:
    x0 = (WIDTH - length) // 2
    x1 = (WIDTH + length) // 2
    draw.rectangle([x0, y, x1, y + thickness], fill=GOLD)


def _draw_diamond(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, alpha: int = 255) -> None:
    color = (GOLD[0], GOLD[1], GOLD[2], alpha)
    draw.polygon([(cx, cy - size), (cx + size, cy), (cx, cy + size), (cx - size, cy)], fill=color)


# ---------------------------------------------------------------------------
# Slide renderers
# ---------------------------------------------------------------------------

def _render_cover(content: dict, filepath: str, layout: str = "oracle") -> None:
    img  = _make_base(seed=1, layout=layout)
    draw = ImageDraw.Draw(img)

    logo_size  = 36 if layout == "minimal" else 48
    logo_color = (CREAM[0], CREAM[1], CREAM[2], 200) if layout == "mystique" else GOLD
    font_logo  = _load_font("Cinzel", "Bold", logo_size)
    bbox = draw.textbbox((0, 0), "[ AURYEL ]", font=font_logo)
    draw.text(((WIDTH - (bbox[2] - bbox[0])) // 2, 100), "[ AURYEL ]", font=font_logo, fill=logo_color)

    title_color = CREAM if layout == "mystique" else WHITE
    font_title  = _load_font("Cinzel", "Bold", 80)
    title       = content.get("title", content.get("titre", ""))
    title_lines = _wrap_text(title, font_title, WIDTH - 120, draw)
    line_h      = draw.textbbox((0, 0), "Ag", font=font_title)[3]
    block_h     = len(title_lines) * (line_h + 16)
    ty          = int(HEIGHT * 0.37) - block_h // 2   # was 0.4 — pulled up
    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=font_title)
        draw.text(((WIDTH - (bbox[2] - bbox[0])) // 2, ty), line, font=font_title, fill=title_color)
        ty += (bbox[3] - bbox[1]) + 16

    if layout == "oracle":
        _draw_gold_line(draw, 1750)
        font_hint = _load_font("Lora", "Regular", 28)
        bbox = draw.textbbox((0, 0), "Glissez →", font=font_hint)
        draw.text(((WIDTH - (bbox[2] - bbox[0])) // 2, 1800), "Glissez →", font=font_hint, fill=GOLD)
    elif layout == "mystique":
        _draw_diamond(draw, WIDTH // 2, 1820, 14, alpha=140)
    # minimal: clean, no bottom decoration

    img.convert("RGB").save(filepath, format="PNG")
    logger.info("[render] 01_cover.png ✓")


def _render_message(content: dict, filepath: str, layout: str = "oracle") -> None:
    img  = _make_base(seed=20, layout=layout)
    draw = ImageDraw.Draw(img)

    title_color = CREAM if layout == "mystique" else WHITE
    body_style  = "Italic" if layout == "mystique" else "Regular"
    body_size   = 48 if layout == "minimal" else 52

    font_title   = _load_font("Cinzel", "Bold", 66)
    title        = content.get("title", "")
    title_bottom = _draw_centered_text(
        draw, title, font_title, title_color, 480, max_width=WIDTH - 120, line_spacing=16  # was 560
    )

    font_body = _load_font("Lora", body_style, body_size)
    body      = content.get("body", "")
    body_y    = max(title_bottom + 60, 650)   # was 70 / 720
    _draw_centered_text(draw, body, font_body, CREAM, body_y, max_width=800, line_spacing=28)  # narrower, more air

    if layout == "oracle":
        _draw_gold_line(draw, 1750, length=200, thickness=4)
    elif layout == "minimal":
        _draw_gold_line(draw, 1750, length=120, thickness=2)
    else:  # mystique
        _draw_diamond(draw, WIDTH // 2, 1790, 12, alpha=150)

    img.convert("RGB").save(filepath, format="PNG")
    logger.info("[render] 02_message.png ✓")


def _render_revelation(content: dict, filepath: str, layout: str = "oracle") -> None:
    sc   = None if layout != "minimal" else 14
    img  = _make_base(seed=30, star_count=sc, layout=layout)
    draw = ImageDraw.Draw(img)
    cx   = WIDTH // 2
    text = content.get("text", content.get("title", ""))

    if layout == "oracle":
        _draw_diamond(draw, cx, 780, 22)
        font    = _load_font("Lora", "Italic", 62)
        y_start = 840
    elif layout == "minimal":
        font    = _load_font("Lora", "Italic", 64)
        y_start = None
    else:  # mystique — triple diamond cluster
        for dx in (-52, 0, 52):
            _draw_diamond(draw, cx + dx, 750, 16)
        font    = _load_font("Lora", "Italic", 64)
        y_start = 820

    lines   = _wrap_text(text, font, WIDTH - 160, draw)
    line_h  = draw.textbbox((0, 0), "Ag", font=font)[3]
    block_h = len(lines) * (line_h + 22)
    y       = max(y_start or 820, (HEIGHT - block_h) // 2)

    text_color = WHITE if layout == "minimal" else CREAM
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        draw.text(((WIDTH - (bbox[2] - bbox[0])) // 2, y), line, font=font, fill=text_color)
        y += (bbox[3] - bbox[1]) + 22

    img.convert("RGB").save(filepath, format="PNG")
    logger.info("[render] 03_revelation.png ✓")


def _render_cta(content: dict, filepath: str, layout: str = "oracle") -> None:
    img  = _make_base(seed=6, layout=layout)
    draw = ImageDraw.Draw(img)

    if layout == "mystique":
        _draw_diamond(draw, WIDTH // 2, 580, 26)   # was 640
        title_y = 660                               # was 720
    else:
        title_y = 640                               # was 700

    font_title   = _load_font("Cinzel", "Bold", 64)
    title        = content.get("title", "")
    title_bottom = _draw_centered_text(
        draw, title, font_title, WHITE, title_y, max_width=WIDTH - 120, line_spacing=18
    )

    line_len   = 200 if layout == "oracle" else (120 if layout == "minimal" else 160)
    line_thick = 2 if layout == "minimal" else 4
    _draw_gold_line(draw, title_bottom + 40, length=line_len, thickness=line_thick)

    cta_text = content.get("cta", "Lien en bio").replace("🔗", "").strip()
    if cta_text:
        cta_size = 52 if layout == "oracle" else 46
        font_cta = _load_font("Lora", "Italic", cta_size)
        _draw_centered_text(
            draw, cta_text, font_cta, GOLD, title_bottom + 100, max_width=WIDTH - 120, line_spacing=14
        )

    font_wm  = _load_font("Lora", "Regular", 24)
    wm_color = (GOLD[0], GOLD[1], GOLD[2], 154)
    bbox = draw.textbbox((0, 0), "Auryel", font=font_wm)
    draw.text(((WIDTH - (bbox[2] - bbox[0])) // 2, 1820), "Auryel", font=font_wm, fill=wm_color)

    img.convert("RGB").save(filepath, format="PNG")
    logger.info("[render] 04_cta.png ✓")


# ---------------------------------------------------------------------------
# Legacy helpers (unused by render_carousel, kept for compatibility)
# ---------------------------------------------------------------------------

def _render_content(content: dict, slide_num: int, filepath: str, filename: str) -> None:
    img  = _make_base(seed=slide_num + 10)
    draw = ImageDraw.Draw(img)
    font_num  = _load_font("Lora", "Regular", 28)
    indicator = f"0{slide_num + 1} / 06"
    bbox = draw.textbbox((0, 0), indicator, font=font_num)
    draw.text(((WIDTH - (bbox[2] - bbox[0])) // 2, 60), indicator, font=font_num, fill=(GOLD[0], GOLD[1], GOLD[2], 128))
    font_title   = _load_font("Cinzel", "Bold", 66)
    title_bottom = _draw_centered_text(draw, content.get("title", ""), font_title, WHITE, 400, max_width=WIDTH - 100, line_spacing=14)
    font_body = _load_font("Lora", "Regular", 54)
    body_y    = max(title_bottom + 60, 650)
    _draw_centered_text(draw, content.get("body", ""), font_body, CREAM, body_y, max_width=840, line_spacing=18)
    _draw_gold_line(draw, 1750)
    img.convert("RGB").save(filepath, format="PNG")


def _render_transition(content: dict, filepath: str) -> None:
    img  = _make_base(seed=99, star_count=45)
    draw = ImageDraw.Draw(img)
    _draw_diamond(draw, WIDTH // 2, 620, 60)
    font_title = _load_font("Cinzel", "Bold", 60)
    _draw_centered_text(draw, content.get("title", ""), font_title, WHITE, 780, max_width=WIDTH - 100, line_spacing=16)
    font_body = _load_font("Lora", "Italic", 40)
    _draw_centered_text(draw, content.get("body", ""), font_body, CREAM, 940, max_width=900, line_spacing=18)
    img.convert("RGB").save(filepath, format="PNG")


def _draw_rounded_rect_filled(draw, cx, cy, w, h, fill_color, radius=50):
    x0, y0 = cx - w // 2, cy - h // 2
    draw.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=radius, fill=fill_color)


def _draw_rounded_rect_outline(draw, cx, cy, w, h, outline_color, width=3, radius=45):
    x0, y0 = cx - w // 2, cy - h // 2
    draw.rounded_rectangle([x0, y0, x0 + w, y0 + h], radius=radius, outline=outline_color, width=width)


# ---------------------------------------------------------------------------
# Preview sheet
# ---------------------------------------------------------------------------

def render_preview_sheet(image_paths: list, output_dir: str) -> str:
    """Assemble 4 slide thumbnails into a 2×2 preview sheet."""
    THUMB_W, THUMB_H = 540, 960
    GAP     = 6
    sheet   = Image.new("RGB", (THUMB_W * 2 + GAP, THUMB_H * 2 + GAP), (5, 5, 12))
    positions = [
        (0, 0),
        (THUMB_W + GAP, 0),
        (0, THUMB_H + GAP),
        (THUMB_W + GAP, THUMB_H + GAP),
    ]
    for i, path in enumerate(image_paths[:4]):
        try:
            thumb = Image.open(path).convert("RGB").resize((THUMB_W, THUMB_H), Image.LANCZOS)
            sheet.paste(thumb, positions[i])
        except Exception as exc:
            logger.warning(f"[preview] Could not load {path}: {exc}")
    out_path = str(Path(output_dir) / "preview_sheet.png")
    sheet.save(out_path, format="PNG")
    logger.info("[render] preview_sheet.png ✓")
    return out_path


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_carousel(content: dict, output_dir: str) -> list[str]:
    """
    Renders 4 PNG slides + preview_sheet.png to output_dir.
    Layout read from content["layout"] (oracle | minimal | mystique).
    Returns list of all rendered paths (slides + preview).
    """
    out    = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    layout = content.get("layout", "oracle")
    slides = content.get("slides", [])
    if len(slides) < 4:
        logger.warning(f"[render] Expected 4 slides, got {len(slides)}")

    file_names  = ["01_cover.png", "02_content_1.png", "03_content_2.png", "04_cta.png"]
    slide_files: list[str] = []

    for idx, slide in enumerate(slides):
        if idx >= 4:
            break
        slide_type = slide.get("type", "")
        filepath   = str(out / file_names[idx])

        if slide_type in ("hook", "cover"):
            _render_cover(slide, filepath, layout)
        elif slide_type in ("message", "content"):
            _render_message(slide, filepath, layout)
        elif slide_type == "revelation":
            _render_revelation(slide, filepath, layout)
        elif slide_type == "cta":
            _render_cta(slide, filepath, layout)
        else:
            logger.warning(f"[render] Unknown slide type '{slide_type}' at index {idx}, skipping.")
            continue

        slide_files.append(filepath)

    preview = render_preview_sheet(slide_files, str(out))
    return slide_files + [preview]
