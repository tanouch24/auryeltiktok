"""
renderer.py — Pillow-based image generation engine for Auryel TikTok carousels.
Renders 6 PNG slides (1080×1920) per content.json dict.
"""

import os
import random
import math
import logging
from pathlib import Path
from typing import Optional

import requests
from PIL import Image, ImageDraw, ImageFont

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

WIDTH = 1080
HEIGHT = 1920

VOID          = (10, 10, 20)        # #0A0A14
VIOLET        = (45, 18, 96)        # #2D1260
ACCENT_VIOLET = (107, 33, 168)      # #6B21A8
GOLD          = (212, 175, 55)      # #D4AF37
GOLD_BRIGHT   = (240, 208, 96)      # #F0D060
WHITE         = (255, 255, 255)
CREAM         = (253, 246, 227)     # #FDF6E3

# ---------------------------------------------------------------------------
# Assets directory
# ---------------------------------------------------------------------------

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
FONTS_DIR  = ASSETS_DIR / "fonts"
FONTS_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Font downloading & caching
# ---------------------------------------------------------------------------

FONT_URLS = {
    # Cinzel is a variable-weight font — one file covers Regular and Bold
    "Cinzel-Regular.ttf":  "https://raw.githubusercontent.com/google/fonts/main/ofl/cinzel/Cinzel%5Bwght%5D.ttf",
    "Cinzel-Bold.ttf":     "https://raw.githubusercontent.com/google/fonts/main/ofl/cinzel/Cinzel%5Bwght%5D.ttf",
    # Lora variable fonts (upright and italic axes)
    "Lora-Regular.ttf":    "https://raw.githubusercontent.com/google/fonts/main/ofl/lora/Lora%5Bwght%5D.ttf",
    "Lora-Italic.ttf":     "https://raw.githubusercontent.com/google/fonts/main/ofl/lora/Lora-Italic%5Bwght%5D.ttf",
}

def _download_font(name: str) -> Optional[Path]:
    """Download a font file to assets/fonts/ if not already present."""
    dest = FONTS_DIR / name
    if dest.exists():
        return dest
    url = FONT_URLS.get(name)
    if not url:
        return None
    try:
        logger.info(f"[fonts] Downloading {name} from {url}")
        r = requests.get(url, timeout=15)
        r.raise_for_status()
        dest.write_bytes(r.content)
        logger.info(f"[fonts] Saved {name} ({len(r.content)//1024} KB)")
        return dest
    except Exception as exc:
        logger.warning(f"[fonts] Failed to download {name}: {exc}")
    return None


def _load_font(family: str, style: str, size: int) -> ImageFont.FreeTypeFont:
    """
    Load a font by family ('Cinzel'|'Lora') and style ('Regular'|'Bold'|'Italic').
    Falls back to PIL default if unavailable.
    """
    name_map = {
        ("Cinzel", "Regular"): "Cinzel-Regular.ttf",
        ("Cinzel", "Bold"):    "Cinzel-Bold.ttf",
        ("Lora",   "Regular"): "Lora-Regular.ttf",
        ("Lora",   "Bold"):    "Lora-Regular.ttf",
        ("Lora",   "Italic"):  "Lora-Italic.ttf",
    }
    key = (family, style)
    if style == "Bold" and family == "Lora":
        logger.warning("[fonts] Lora Bold unavailable, using Regular")
    filename = name_map.get(key, name_map.get((family, "Regular")))
    if filename:
        path = _download_font(filename)
        if path and path.exists():
            try:
                return ImageFont.truetype(str(path), size)
            except Exception as exc:
                logger.warning(f"[fonts] truetype load failed for {path}: {exc}")
    # fallback
    try:
        return ImageFont.load_default(size=size)
    except TypeError:
        return ImageFont.load_default()


# ---------------------------------------------------------------------------
# Drawing helpers
# ---------------------------------------------------------------------------

def _draw_radial_gradient(img: Image.Image) -> None:
    """
    Simulate a radial gradient: center=VIOLET (#2D1260) → outer=VOID (#0A0A14).
    Uses 120 concentric ellipses drawn from outermost (dark) to innermost (violet).
    """
    draw = ImageDraw.Draw(img)
    steps = 120
    cx, cy = WIDTH // 2, HEIGHT // 2
    max_rx = int(math.sqrt(cx**2 + cy**2)) + 20  # covers corners

    for i in range(steps):
        t = i / (steps - 1)           # 0 = outer (VOID), 1 = inner (VIOLET)
        r = int(VOID[0] + (VIOLET[0] - VOID[0]) * t)
        g = int(VOID[1] + (VIOLET[1] - VOID[1]) * t)
        b = int(VOID[2] + (VIOLET[2] - VOID[2]) * t)

        # ellipse radius decreases as i grows (outer first)
        rx = int(max_rx * (1 - t * 0.65))
        ry = int(max_rx * (1 - t * 0.55))

        x0, y0 = cx - rx, cy - ry
        x1, y1 = cx + rx, cy + ry
        draw.ellipse([x0, y0, x1, y1], fill=(r, g, b))


def _draw_stars(img: Image.Image, seed: int = 42, count: int = 40) -> None:
    """Scatter semi-transparent golden stars (small dots/diamonds) across the image."""
    draw = ImageDraw.Draw(img)
    rng = random.Random(seed)

    for _ in range(count):
        x = rng.randint(20, WIDTH - 20)
        y = rng.randint(20, HEIGHT - 20)
        size = rng.randint(2, 4)
        shape = rng.choice(["dot", "diamond"])

        # Simulate alpha by blending gold toward the background color at that point
        alpha = rng.randint(140, 220)
        color = (GOLD[0], GOLD[1], GOLD[2], alpha)

        if shape == "dot":
            draw.ellipse([x - size, y - size, x + size, y + size], fill=color)
        else:
            # diamond
            draw.polygon(
                [(x, y - size * 2), (x + size, y), (x, y + size * 2), (x - size, y)],
                fill=color,
            )


def _make_base(seed: int = 42, star_count: Optional[int] = None) -> Image.Image:
    """Create a base image with radial gradient + stars."""
    img = Image.new("RGBA", (WIDTH, HEIGHT), VOID)
    _draw_radial_gradient(img)
    count = star_count if star_count is not None else random.Random(seed).randint(30, 50)
    _draw_stars(img, seed=seed, count=count)
    return img


def _wrap_text(text: str, font: ImageFont.FreeTypeFont, max_width: int, draw: ImageDraw.ImageDraw) -> list[str]:
    """Word-wrap text to fit within max_width pixels. Returns list of lines."""
    words = text.split()
    lines = []
    current_line = []
    for word in words:
        test_line = " ".join(current_line + [word])
        bbox = draw.textbbox((0, 0), test_line, font=font)
        w = bbox[2] - bbox[0]
        if w <= max_width:
            current_line.append(word)
        else:
            if current_line:
                lines.append(" ".join(current_line))
                current_line = [word]
            else:
                # single word too long — accept it
                lines.append(word)
    if current_line:
        lines.append(" ".join(current_line))
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
    """
    Draw word-wrapped centered text starting at y. Returns the y position after last line.
    """
    lines = _wrap_text(text, font, max_width, draw)
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        w = bbox[2] - bbox[0]
        x = (WIDTH - w) // 2
        draw.text((x, y), line, font=font, fill=color)
        y += (bbox[3] - bbox[1]) + line_spacing
    return y


def _draw_gold_line(draw: ImageDraw.ImageDraw, y: int, length: int = 200, thickness: int = 4) -> None:
    """Draw a centered horizontal gold line."""
    x0 = (WIDTH - length) // 2
    x1 = (WIDTH + length) // 2
    draw.rectangle([x0, y, x1, y + thickness], fill=GOLD)


def _draw_rounded_rect_filled(
    draw: ImageDraw.ImageDraw,
    cx: int, cy: int, w: int, h: int,
    fill_color: tuple, radius: int = 50
) -> None:
    """Draw a filled rounded rectangle centered at (cx, cy)."""
    x0, y0 = cx - w // 2, cy - h // 2
    x1, y1 = cx + w // 2, cy + h // 2
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, fill=fill_color)


def _draw_rounded_rect_outline(
    draw: ImageDraw.ImageDraw,
    cx: int, cy: int, w: int, h: int,
    outline_color: tuple, width: int = 3, radius: int = 45
) -> None:
    """Draw an outlined rounded rectangle centered at (cx, cy)."""
    x0, y0 = cx - w // 2, cy - h // 2
    x1, y1 = cx + w // 2, cy + h // 2
    draw.rounded_rectangle([x0, y0, x1, y1], radius=radius, outline=outline_color, width=width)


# ---------------------------------------------------------------------------
# Slide renderers
# ---------------------------------------------------------------------------

def _render_cover(content: dict, filepath: str) -> None:
    img = _make_base(seed=1)
    draw = ImageDraw.Draw(img)

    # Logo "✦ AURYEL ✦"
    font_logo = _load_font("Cinzel", "Bold", 48)
    logo_text = "✦ AURYEL ✦"
    bbox = draw.textbbox((0, 0), logo_text, font=font_logo)
    x = (WIDTH - (bbox[2] - bbox[0])) // 2
    draw.text((x, 100), logo_text, font=font_logo, fill=GOLD)

    # Main title — vertically centered at ~40% height (~768)
    font_title = _load_font("Cinzel", "Bold", 64)
    title = content.get("title", "")
    title_lines = _wrap_text(title, font_title, WIDTH - 120, draw)
    # measure total block height
    line_h = draw.textbbox((0, 0), "Ag", font=font_title)[3]
    block_h = len(title_lines) * (line_h + 16)
    title_y = int(HEIGHT * 0.4) - block_h // 2
    for line in title_lines:
        bbox = draw.textbbox((0, 0), line, font=font_title)
        x = (WIDTH - (bbox[2] - bbox[0])) // 2
        draw.text((x, title_y), line, font=font_title, fill=WHITE)
        title_y += (bbox[3] - bbox[1]) + 16

    # Subtitle
    font_sub = _load_font("Lora", "Italic", 36)
    subtitle = content.get("subtitle", "")
    sub_y = title_y + 40
    _draw_centered_text(draw, subtitle, font_sub, CREAM, sub_y, max_width=WIDTH - 140, line_spacing=14)

    # Decorative gold line
    _draw_gold_line(draw, 1750)

    # "Glissez →"
    font_hint = _load_font("Lora", "Regular", 28)
    hint = "Glissez →"
    bbox = draw.textbbox((0, 0), hint, font=font_hint)
    x = (WIDTH - (bbox[2] - bbox[0])) // 2
    draw.text((x, 1800), hint, font=font_hint, fill=GOLD)

    img.convert("RGB").save(filepath, format="PNG")
    logger.info(f"[render] 01_cover.png ✓")


def _render_content(content: dict, slide_num: int, filepath: str, filename: str) -> None:
    img = _make_base(seed=slide_num + 10)
    draw = ImageDraw.Draw(img)

    total = 6  # total slides in carousel

    # Slide number indicator
    font_num = _load_font("Lora", "Regular", 28)
    indicator = f"0{slide_num + 1} / 0{total}"
    bbox = draw.textbbox((0, 0), indicator, font=font_num)
    x = (WIDTH - (bbox[2] - bbox[0])) // 2
    # semi-transparent via blending: draw on RGBA overlay
    indicator_color = (GOLD[0], GOLD[1], GOLD[2], 128)
    draw.text((x, 60), indicator, font=font_num, fill=indicator_color)

    # Icon/emoji
    font_icon = _load_font("Lora", "Regular", 96)
    icon = content.get("icon", "✨")
    bbox = draw.textbbox((0, 0), icon, font=font_icon)
    x = (WIDTH - (bbox[2] - bbox[0])) // 2
    draw.text((x, 240), icon, font=font_icon, fill=WHITE)

    # Title
    font_title = _load_font("Cinzel", "Bold", 52)
    title = content.get("title", "")
    title_bottom = _draw_centered_text(draw, title, font_title, WHITE, 400, max_width=WIDTH - 100, line_spacing=14)

    # Body — starts below actual title bottom to avoid overlap
    font_body = _load_font("Lora", "Regular", 38)
    body = content.get("body", "")
    body_y = max(title_bottom + 30, 570)
    _draw_centered_text(draw, body, font_body, CREAM, body_y, max_width=900, line_spacing=18)

    # Decorative gold line
    _draw_gold_line(draw, 1750)

    img.convert("RGB").save(filepath, format="PNG")
    logger.info(f"[render] {filename} ✓")


def _render_transition(content: dict, filepath: str) -> None:
    img = _make_base(seed=99, star_count=45)
    draw = ImageDraw.Draw(img)

    # Large decorative symbol
    font_symbol = _load_font("Cinzel", "Regular", 128)
    symbol = "✦"
    bbox = draw.textbbox((0, 0), symbol, font=font_symbol)
    x = (WIDTH - (bbox[2] - bbox[0])) // 2
    draw.text((x, 560), symbol, font=font_symbol, fill=GOLD)

    # Title
    font_title = _load_font("Cinzel", "Bold", 60)
    title = content.get("title", "")
    _draw_centered_text(draw, title, font_title, WHITE, 780, max_width=WIDTH - 100, line_spacing=16)

    # Body
    font_body = _load_font("Lora", "Italic", 40)
    body = content.get("body", "")
    _draw_centered_text(draw, body, font_body, CREAM, 940, max_width=900, line_spacing=18)

    img.convert("RGB").save(filepath, format="PNG")
    logger.info(f"[render] 05_transition.png ✓")


def _render_cta(content: dict, filepath: str) -> None:
    img = _make_base(seed=6)
    draw = ImageDraw.Draw(img)

    # Title
    font_title = _load_font("Cinzel", "Bold", 56)
    title = content.get("title", "")
    _draw_centered_text(draw, title, font_title, WHITE, 640, max_width=WIDTH - 100, line_spacing=16)

    cx = WIDTH // 2

    # CTA button 1 — filled violet
    _draw_rounded_rect_filled(draw, cx, 950, 800, 100, ACCENT_VIOLET, radius=50)
    font_cta1 = _load_font("Lora", "Bold", 40)
    cta1 = content.get("cta1", "💬 Parler à mon guide")
    bbox = draw.textbbox((0, 0), cta1, font=font_cta1)
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - bw // 2, 950 - bh // 2), cta1, font=font_cta1, fill=WHITE)

    # CTA button 2 — outlined gold
    _draw_rounded_rect_outline(draw, cx, 1100, 700, 90, GOLD, width=3, radius=45)
    font_cta2 = _load_font("Lora", "Regular", 36)
    cta2 = content.get("cta2", "✨ auryel.fr")
    bbox = draw.textbbox((0, 0), cta2, font=font_cta2)
    bw, bh = bbox[2] - bbox[0], bbox[3] - bbox[1]
    draw.text((cx - bw // 2, 1100 - bh // 2), cta2, font=font_cta2, fill=GOLD)

    # Watermark "Auryel ✦"
    font_wm = _load_font("Lora", "Regular", 24)
    wm = "Auryel ✦"
    wm_color = (GOLD[0], GOLD[1], GOLD[2], 154)  # 60% of 255 ≈ 154
    bbox = draw.textbbox((0, 0), wm, font=font_wm)
    x = (WIDTH - (bbox[2] - bbox[0])) // 2
    draw.text((x, 1750), wm, font=font_wm, fill=wm_color)

    img.convert("RGB").save(filepath, format="PNG")
    logger.info(f"[render] 06_cta.png ✓")


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def render_carousel(content: dict, output_dir: str) -> list[str]:
    """
    Renders 6 PNG slides to output_dir based on content dict.

    Args:
        content: Parsed content.json dict with 'slides' list.
        output_dir: Directory path where PNG files will be written.

    Returns:
        List of absolute file paths for the 6 rendered PNGs.
    """
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    slides = content.get("slides", [])
    if len(slides) < 6:
        logger.warning(f"[render] Expected 6 slides, got {len(slides)} — output will be incomplete")
    output_files: list[str] = []

    # Map slide types to filenames and renderers
    file_names = [
        "01_cover.png",
        "02_slide.png",
        "03_slide.png",
        "04_slide.png",
        "05_transition.png",
        "06_cta.png",
    ]

    content_slide_num = 1  # counter for content slides (1-3)

    for idx, slide in enumerate(slides):
        if idx >= 6:
            break
        slide_type = slide.get("type", "content")
        filename = file_names[idx]
        filepath = str(out / filename)

        if slide_type == "cover":
            _render_cover(slide, filepath)
        elif slide_type == "content":
            _render_content(slide, content_slide_num, filepath, filename)
            content_slide_num += 1
        elif slide_type == "transition":
            _render_transition(slide, filepath)
        elif slide_type == "cta":
            _render_cta(slide, filepath)
        else:
            logger.warning(f"[render] Unknown slide type '{slide_type}' at index {idx}, skipping.")
            continue

        output_files.append(filepath)

    return output_files
