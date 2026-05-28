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
SILVER        = (200, 210, 230)
SILVER_BRIGHT = (230, 238, 255)
COSMIC_BLUE   = (80, 120, 220)
DARK_NAVY     = (4,  6,  18)

# WhatsApp dark theme palette
_WA_BG         = (11,  20,  26)
_WA_HEADER_BG  = (31,  44,  52)
_WA_BUBBLE_USR = (0,   91,  74)
_WA_BUBBLE_AUR = (31,  44,  52)
_WA_TEXT       = (229, 229, 229)
_WA_TIME_C     = (132, 148, 152)
_WA_SEEN_C     = (83,  178, 153)
_WA_AVATAR_BG  = (70,  10,  140)
_WA_NAME_C     = (100, 196, 172)
_WA_DATE_BG    = (20,  30,  38)
_WA_DATE_C     = (132, 148, 152)

# Radial gradient parameters per layout
_LAYOUT_GRADIENT = {
    "oracle":    {"center": (45, 18, 96),  "outer": (10, 10, 20)},
    "minimal":   {"center": (18, 8,  38),  "outer": (8,  6,  14)},
    "mystique":  {"center": (70, 22, 118), "outer": (6,  3,  16)},
    "lune":      {"center": (10, 10, 34),  "outer": (2,  2,  8)},   # near-black navy
    "tarot":     {"center": (22, 14, 8),   "outer": (4,  4,  4)},   # warm charcoal
    "cosmique":  {"center": (22, 8,  72),  "outer": (4,  2,  22)},  # deep cosmic purple
    "silhouette":{"center": (38, 8,  62),  "outer": (6,  2,  14)},  # deep violet-black
}

# Star density per layout — reduced 35% vs original for cleaner depth
_LAYOUT_STARS = {
    "oracle":    (32, 42),
    "minimal":   (6,  11),
    "mystique":  (18, 26),
    "lune":      (10, 16),   # sparse silver
    "tarot":     (3,  7),    # near-empty, gold only
    "cosmique":  (68, 88),   # dense nebula feel
    "silhouette":(18, 24),   # sparse gold
}

# Focal element positions per layout (cx, cy)
_FOCAL_POSITIONS = {
    "oracle":    (793, 282),   # warm gold glow, upper right
    "minimal":   (728, 232),   # cool white glow, upper right
    "mystique":  (322, 302),   # violet-white glow, upper left
    "lune":      (540, 360),   # moon centered upper zone
    "tarot":     (540, 400),   # centered gold element
    "cosmique":  (540, 480),   # centered nebula core
    "silhouette":(620, 460),   # silhouette head zone, slight right
}

# ---------------------------------------------------------------------------
# Assets
# ---------------------------------------------------------------------------

ASSETS_DIR = Path(__file__).resolve().parent.parent / "assets"
FONTS_DIR  = ASSETS_DIR / "fonts"
FONTS_DIR.mkdir(parents=True, exist_ok=True)

FONT_URLS = {
    # ── Hook display font — condensed, maximum impact ─────────────────────
    "Oswald-Bold.ttf":         "https://raw.githubusercontent.com/google/fonts/main/ofl/oswald/Oswald%5Bwght%5D.ttf",
    "Oswald-SemiBold.ttf":     "https://raw.githubusercontent.com/google/fonts/main/ofl/oswald/Oswald%5Bwght%5D.ttf",
    # ── Secondary — clean modern sans-serif ──────────────────────────────
    "Montserrat-Bold.ttf":     "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf",
    "Montserrat-SemiBold.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf",
    "Montserrat-Regular.ttf":  "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat%5Bwght%5D.ttf",
    "Montserrat-Italic.ttf":   "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat-Italic%5Bwght%5D.ttf",
    "Montserrat-LightItalic.ttf": "https://raw.githubusercontent.com/google/fonts/main/ofl/montserrat/Montserrat-Italic%5Bwght%5D.ttf",
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
        # ── Hook display font (Oswald condensed) ─────────────────────────
        ("Oswald",      "Bold"):        "Oswald-Bold.ttf",
        ("Oswald",      "SemiBold"):    "Oswald-SemiBold.ttf",
        ("Oswald",      "Regular"):     "Oswald-SemiBold.ttf",
        # ── Secondary font (Montserrat) ───────────────────────────────────
        ("Montserrat",  "Bold"):        "Montserrat-Bold.ttf",
        ("Montserrat",  "SemiBold"):    "Montserrat-SemiBold.ttf",
        ("Montserrat",  "Regular"):     "Montserrat-Regular.ttf",
        ("Montserrat",  "Italic"):      "Montserrat-Italic.ttf",
        ("Montserrat",  "LightItalic"): "Montserrat-LightItalic.ttf",
        # ── Legacy aliases (old generators may still reference these) ─────
        ("Cinzel",      "Bold"):        "Oswald-Bold.ttf",
        ("Cinzel",      "Regular"):     "Montserrat-SemiBold.ttf",
        ("Lora",        "Regular"):     "Montserrat-Regular.ttf",
        ("Lora",        "Italic"):      "Montserrat-Italic.ttf",
        ("Lora",        "Bold"):        "Montserrat-Bold.ttf",
    }
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
    cx, cy = WIDTH // 2, HEIGHT // 2 + 80   # shifted down — visual tension toward CTA
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

    # Choose star palette per layout
    if layout == "lune":
        base_color = SILVER
    elif layout in ("tarot", "oracle", "silhouette"):
        base_color = GOLD
    elif layout == "cosmique":
        base_color = SILVER_BRIGHT
    else:
        base_color = GOLD

    for _ in range(count):
        x = rng.randint(20, WIDTH - 20)
        y = rng.randint(20, HEIGHT - 20)
        is_distant = rng.random() < 0.70

        if layout == "minimal":
            size  = 1 if is_distant else rng.randint(2, 3)
            shape = "dot"
            alpha = rng.randint(40, 80) if is_distant else rng.randint(90, 140)
        elif layout in ("mystique", "silhouette"):
            size  = 1 if is_distant else rng.randint(2, 4)
            shape = "dot" if is_distant else rng.choice(["dot", "diamond"])
            alpha = rng.randint(45, 90) if is_distant else rng.randint(130, 195)
        elif layout == "lune":
            size  = 1 if is_distant else rng.randint(2, 3)
            shape = "dot"
            alpha = rng.randint(30, 65) if is_distant else rng.randint(90, 160)
        elif layout == "tarot":
            size  = rng.randint(1, 2) if is_distant else rng.randint(2, 4)
            shape = "dot" if is_distant else rng.choice(["dot", "diamond"])
            alpha = rng.randint(60, 100) if is_distant else rng.randint(160, 230)
        elif layout == "cosmique":
            size  = rng.randint(1, 2) if is_distant else rng.randint(2, 4)
            shape = "dot" if is_distant else rng.choice(["dot", "diamond"])
            alpha = rng.randint(35, 70) if is_distant else rng.randint(100, 180)
        else:  # oracle
            size  = rng.randint(1, 2) if is_distant else rng.randint(3, 5)
            shape = "dot" if is_distant else rng.choice(["dot", "diamond"])
            alpha = rng.randint(50, 95) if is_distant else rng.randint(155, 220)

        color = (*base_color[:3], alpha)
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
    """Atmospheric focal element in the upper breathing zone, per layout."""
    cx, cy = _FOCAL_POSITIONS.get(layout, (780, 340))

    if layout == "lune":
        _draw_moon(img, cx, cy)
        return
    if layout == "cosmique":
        _draw_nebula(img, cx, cy)
        return
    if layout == "silhouette":
        _draw_silhouette_figure(img)
        return

    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)

    if layout == "minimal":
        layers = [(72, 4), (46, 7), (24, 10), (10, 13)]
        base   = (230, 230, 255)
    elif layout == "mystique":
        layers = [(88, 3), (58, 7), (30, 10), (12, 14)]
        base   = (200, 180, 255)
    elif layout == "tarot":
        # Large central golden diamond glow
        layers = [(90, 4), (60, 8), (34, 14), (14, 20)]
        base   = (240, 200, 80)
    else:  # oracle
        layers = [(80, 5), (52, 8), (26, 13), (10, 17)]
        base   = (245, 215, 130)

    for radius, alpha in layers:
        draw.ellipse([cx - radius, cy - radius, cx + radius, cy + radius],
                     fill=(*base, alpha))
    img.alpha_composite(overlay)


# ---------------------------------------------------------------------------
# New layout-specific decorators
# ---------------------------------------------------------------------------

def _draw_moon(img: Image.Image, cx: int, cy: int) -> None:
    """Large soft moon disc with layered silver glow — used by 'lune' layout."""
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)
    # Outer glow layers
    for r, a in [(180, 6), (140, 10), (106, 18), (80, 30), (62, 60)]:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                     fill=(SILVER_BRIGHT[0], SILVER_BRIGHT[1], SILVER_BRIGHT[2], a))
    # Moon disc
    r = 50
    draw.ellipse([cx - r, cy - r, cx + r, cy + r], fill=(230, 238, 255, 200))
    # Subtle crescent shadow (offset disc)
    shadow_r = 44
    dx, dy   = 16, -10
    draw.ellipse([cx - shadow_r + dx, cy - shadow_r + dy,
                  cx + shadow_r + dx, cy + shadow_r + dy],
                 fill=(8, 8, 24, 180))
    img.alpha_composite(overlay)


def _draw_tarot_border(img: Image.Image) -> None:
    """Thick double-line gold border with corner ornaments — 'tarot' layout."""
    draw = ImageDraw.Draw(img)
    inset, thick = 18, 3
    x0, y0, x1, y1 = inset, inset, WIDTH - inset, HEIGHT - inset
    c = (GOLD_BRIGHT[0], GOLD_BRIGHT[1], GOLD_BRIGHT[2], 220)
    # Outer frame
    draw.rectangle([x0, y0, x1, y0 + thick], fill=c)
    draw.rectangle([x0, y1 - thick, x1, y1],   fill=c)
    draw.rectangle([x0, y0, x0 + thick, y1],   fill=c)
    draw.rectangle([x1 - thick, y0, x1, y1],   fill=c)
    # Inner frame (offset)
    gap = 10
    draw.rectangle([x0 + gap, y0 + gap, x1 - gap, y0 + gap + 1], fill=(GOLD[0], GOLD[1], GOLD[2], 100))
    draw.rectangle([x0 + gap, y1 - gap - 1, x1 - gap, y1 - gap],  fill=(GOLD[0], GOLD[1], GOLD[2], 100))
    draw.rectangle([x0 + gap, y0 + gap, x0 + gap + 1, y1 - gap],  fill=(GOLD[0], GOLD[1], GOLD[2], 100))
    draw.rectangle([x1 - gap - 1, y0 + gap, x1 - gap, y1 - gap],  fill=(GOLD[0], GOLD[1], GOLD[2], 100))
    # Corner diamond ornaments
    for cx, cy in [(x0 + 14, y0 + 14), (x1 - 14, y0 + 14),
                   (x0 + 14, y1 - 14), (x1 - 14, y1 - 14)]:
        _draw_diamond(draw, cx, cy, 7, alpha=240)


def _draw_nebula(img: Image.Image, cx: int, cy: int) -> None:
    """Multi-layered nebula glow — 'cosmique' layout."""
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)
    layers = [
        (380, 260, ACCENT_VIOLET, 8),
        (290, 200, (60, 30, 160), 12),
        (210, 160, COSMIC_BLUE,   10),
        (140, 120, (120, 60, 200), 14),
        (80,   70, SILVER_BRIGHT,  8),
    ]
    for rx, ry, color, alpha in layers:
        draw.ellipse([cx - rx, cy - ry, cx + rx, cy + ry],
                     fill=(*color, alpha))
    img.alpha_composite(overlay)


def _draw_silhouette_figure(img: Image.Image) -> None:
    """
    Feminine presence — cinématographique, jamais kitsch.
    Silhouette sombre avec rim light violet, yeux lumineux subtils, halo de cheveux.
    """
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)

    cx, cy = 650, 510   # centre tête
    hr     = 148        # rayon tête

    # --- Corps / épaules (masse sombre en dessous) ---
    sw = 248
    draw.ellipse([cx - sw, cy + hr + 5, cx + sw, cy + hr + 5 + 230],
                 fill=(8, 3, 14, 115))

    # --- Cou ---
    nw = 38
    draw.rectangle([cx - nw, cy + hr - 15, cx + nw, cy + hr + 85],
                   fill=(10, 4, 16, 140))

    # --- Tête (remplissage sombre — légèrement différent du fond) ---
    draw.ellipse([cx - hr, cy - hr, cx + hr, cy + hr], fill=(15, 5, 24, 195))

    # --- Rim light principal : halo violet dégradé ---
    rim_layers = [
        (hr + 46, 3),
        (hr + 34, 7),
        (hr + 22, 14),
        (hr + 12, 22),
        (hr +  5, 30),
    ]
    for r, a in rim_layers:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                     fill=(155, 80, 255, a))

    # --- Halo de cheveux (top de la tête) — lumière dorée subtile ---
    hair_layers = [(hr + 24, 5), (hr + 14, 10), (hr + 6, 8)]
    for r, a in hair_layers:
        # Demi-ellipse supérieure seulement
        draw.ellipse([cx - r, cy - hr - 18, cx + r, cy - hr + int(r * 0.5)],
                     fill=(GOLD[0], GOLD[1], GOLD[2], a))

    # --- Yeux lumineux (à peine visibles — mystérieux) ---
    eye_sep = 46
    eye_y   = cy - 24
    for ex in [cx - eye_sep, cx + eye_sep]:
        # Glow externe très doux
        for r, a in [(18, 4), (11, 10), (5, 22), (2, 48)]:
            h2 = max(1, r // 2)
            draw.ellipse([ex - r, eye_y - h2, ex + r, eye_y + h2],
                         fill=(220, 185, 130, a))
        # Point central lumineux
        draw.ellipse([ex - 2, eye_y - 1, ex + 2, eye_y + 1],
                     fill=(255, 240, 210, 100))

    # --- Arc gold — contour latéral (lumière cinéma) ---
    r_arc = hr + 6
    draw.arc([cx - r_arc, cy - r_arc, cx + r_arc, cy + r_arc],
             start=195, end=345,
             fill=(GOLD_BRIGHT[0], GOLD_BRIGHT[1], GOLD_BRIGHT[2], 70), width=2)

    img.alpha_composite(overlay)


def _draw_eye_glow(img: Image.Image, cx: int, cy: int) -> None:
    """Geometric eye element — used optionally in mystique/silhouette layouts."""
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)
    for r, a in [(36, 8), (22, 18), (12, 35), (5, 70)]:
        draw.ellipse([cx - r, cy - r, cx + r, cy + r],
                     fill=(GOLD_BRIGHT[0], GOLD_BRIGHT[1], GOLD_BRIGHT[2], a))
    img.alpha_composite(overlay)


def _draw_smoke_wisps(img: Image.Image, seed: int = 42, count: int = 5,
                      opacity: int = 35) -> None:
    """
    Traînées de fumée/brume horizontales — effet cinématographique subtil.
    Utilisé sur lune, mystique, silhouette pour ajouter de la profondeur.
    """
    overlay = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
    draw    = ImageDraw.Draw(overlay)
    rng     = random.Random(seed + 777)

    for _ in range(count):
        # Wisp : ellipse très allongée horizontalement
        cx  = rng.randint(100, WIDTH - 100)
        cy  = rng.randint(900, 1600)           # zone basse/milieu
        rx  = rng.randint(160, 340)
        ry  = rng.randint(6, 18)
        a   = rng.randint(8, opacity)

        # Décalage léger pour superposition naturelle
        for dy in range(-1, 2):
            draw.ellipse([cx - rx, cy - ry + dy * 5,
                          cx + rx, cy + ry + dy * 5],
                         fill=(SILVER[0], SILVER[1], SILVER[2], max(3, a - abs(dy) * 8)))

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
        _draw_smoke_wisps(img, seed=seed + 11, count=4, opacity=28)
    elif layout == "tarot":
        _draw_tarot_border(img)
    elif layout == "silhouette":
        _draw_border_frame(img)
        _draw_smoke_wisps(img, seed=seed + 33, count=5, opacity=32)
    elif layout == "lune":
        _draw_smoke_wisps(img, seed=seed + 55, count=6, opacity=40)
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
    # Anti-widow: last line must have ≥2 words
    if len(lines) > 1 and len(lines[-1].split()) == 1:
        prev = lines[-2].split()
        if len(prev) > 1:
            lines[-2] = " ".join(prev[:-1])
            lines[-1] = prev[-1] + " " + lines[-1]
    return lines


def _wrap_text_balanced(text: str, font: ImageFont.FreeTypeFont,
                        max_width: int, draw: ImageDraw.ImageDraw,
                        max_lines: int = 2) -> list[str]:
    """Balanced line wrap — minimises width difference between lines.
    Prevents single-word orphans and uneven blocks. Falls back to greedy."""
    words = text.split()
    if not words:
        return [""]
    if draw.textbbox((0, 0), text, font=font)[2] <= max_width:
        return [text]

    best_lines: Optional[list[str]] = None
    best_diff = float("inf")
    for split in range(1, len(words)):
        l1 = " ".join(words[:split])
        l2 = " ".join(words[split:])
        w1 = draw.textbbox((0, 0), l1, font=font)[2]
        w2 = draw.textbbox((0, 0), l2, font=font)[2]
        if w1 <= max_width and w2 <= max_width:
            diff = abs(w1 - w2)
            if diff < best_diff:
                best_diff = diff
                best_lines = [l1, l2]

    if best_lines:
        return best_lines
    return _wrap_text(text, font, max_width, draw)[:max_lines]


def _pick_hook_size(text: str, draw: ImageDraw.ImageDraw, max_width: int) -> ImageFont.FreeTypeFont:
    """Return largest Oswald Bold size where text wraps to ≤ 2 balanced lines."""
    for size in (96, 82, 70, 60):
        font = _load_font("Oswald", "Bold", size)
        if len(_wrap_text(text, font, max_width, draw)) <= 2:
            return font
    return _load_font("Oswald", "Bold", 60)


def _pick_reveal_size(text: str, draw: ImageDraw.ImageDraw, max_width: int) -> ImageFont.FreeTypeFont:
    """Return largest Oswald SemiBold size where revelation fits in ≤ 2 lines."""
    for size in (88, 74, 62):
        font = _load_font("Oswald", "SemiBold", size)
        if len(_wrap_text(text, font, max_width, draw)) <= 2:
            return font
    return _load_font("Oswald", "SemiBold", 62)


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    font: ImageFont.FreeTypeFont,
    color: tuple,
    y: int,
    max_width: int = WIDTH - 80,
    line_spacing: int = 20,
    max_lines: int = 0,
    tracking: float = 0.0,
    stroke_width: int = 0,
    stroke_fill: Optional[tuple] = None,
) -> int:
    """Draw word-wrapped centered text. Returns y after last line."""
    lines = _wrap_text(text, font, max_width, draw)
    if max_lines:
        lines = lines[:max_lines]
    for line in lines:
        line_h = _draw_line_centered(draw, line, font, color, y,
                                     tracking=tracking, stroke_width=stroke_width,
                                     stroke_fill=stroke_fill)
        y += line_h + line_spacing
    return y


def _draw_gold_line(draw: ImageDraw.ImageDraw, y: int, length: int = 200, thickness: int = 4) -> None:
    x0 = (WIDTH - length) // 2
    x1 = (WIDTH + length) // 2
    draw.rectangle([x0, y, x1, y + thickness], fill=GOLD)


def _draw_diamond(draw: ImageDraw.ImageDraw, cx: int, cy: int, size: int, alpha: int = 255) -> None:
    color = (GOLD[0], GOLD[1], GOLD[2], alpha)
    draw.polygon([(cx, cy - size), (cx + size, cy), (cx, cy + size), (cx - size, cy)], fill=color)


def _draw_line_centered(
    draw: ImageDraw.ImageDraw,
    line: str,
    font: ImageFont.FreeTypeFont,
    color: tuple,
    y: int,
    tracking: float = 0.0,
    stroke_width: int = 0,
    stroke_fill: Optional[tuple] = None,
) -> int:
    """Draw a single centered line with optional tracking and stroke. Returns line height."""
    if not line:
        bb = draw.textbbox((0, 0), "Ag", font=font)
        return bb[3] - bb[1]
    if tracking != 0.0:
        chars = list(line)
        bboxes = [draw.textbbox((0, 0), ch, font=font) for ch in chars]
        char_widths = [bb[2] - bb[0] for bb in bboxes]
        char_h = max(bb[3] - bb[1] for bb in bboxes)
        avg_w = sum(char_widths) / len(chars)
        kern = avg_w * tracking
        total_w = sum(char_widths) + kern * max(0, len(chars) - 1)
        x = (WIDTH - total_w) / 2
        kw: dict = {"font": font, "fill": color}
        if stroke_width and stroke_fill:
            kw["stroke_width"] = stroke_width
            kw["stroke_fill"] = stroke_fill
        for ch, cw in zip(chars, char_widths):
            draw.text((int(x), y), ch, **kw)
            x += cw + kern
    else:
        bbox = draw.textbbox((0, 0), line, font=font)
        char_h = bbox[3] - bbox[1]
        x = (WIDTH - (bbox[2] - bbox[0])) // 2
        kw = {"font": font, "fill": color}
        if stroke_width and stroke_fill:
            kw["stroke_width"] = stroke_width
            kw["stroke_fill"] = stroke_fill
        draw.text((x, y), line, **kw)
    return char_h


# ---------------------------------------------------------------------------
# Slide renderers
# ---------------------------------------------------------------------------

def _render_cover(content: dict, filepath: str, layout: str = "oracle",
                  seed_offset: int = 0) -> None:
    img  = _make_base(seed=1 + seed_offset, layout=layout)
    draw = ImageDraw.Draw(img)
    # Micro-variation verticale : -25 / 0 / +25 px selon le variant du jour
    _y_delta = [-25, 0, 25][seed_offset % 3]

    # ── Logo — Montserrat SemiBold, letter-spaced, top center ──────────────
    logo_size = 30 if layout in ("minimal", "lune") else 34
    if layout in ("mystique", "silhouette"):
        logo_color = (CREAM[0], CREAM[1], CREAM[2], 160)
    elif layout == "lune":
        logo_color = (SILVER[0], SILVER[1], SILVER[2], 140)
    elif layout == "tarot":
        logo_color = (GOLD_BRIGHT[0], GOLD_BRIGHT[1], GOLD_BRIGHT[2], 190)
    elif layout == "cosmique":
        logo_color = (SILVER_BRIGHT[0], SILVER_BRIGHT[1], SILVER_BRIGHT[2], 160)
    else:
        logo_color = (GOLD[0], GOLD[1], GOLD[2], 200)
    font_logo = _load_font("Montserrat", "SemiBold", logo_size)
    logo_text = "A U R Y E L"
    bbox = draw.textbbox((0, 0), logo_text, font=font_logo)
    draw.text(((WIDTH - (bbox[2] - bbox[0])) // 2, 112), logo_text, font=font_logo, fill=logo_color)

    # ── Hook title — Oswald Bold, adaptive size, balanced wrap ─────────────
    if layout in ("mystique", "silhouette", "lune"):
        title_color = CREAM
    elif layout == "tarot":
        title_color = GOLD_BRIGHT
    else:
        title_color = WHITE

    hook_max_w  = WIDTH - 100          # 980px — generous but safe margin
    title       = content.get("title", content.get("titre", ""))
    font_title  = _pick_hook_size(title, draw, hook_max_w)
    title_lines = _wrap_text_balanced(title, font_title, hook_max_w, draw, max_lines=2)

    _bb     = draw.textbbox((0, 0), "Ag", font=font_title)
    line_h  = _bb[3] - _bb[1]
    spacing = max(10, int(line_h * 0.13))   # ~13% of cap-height — clean air
    block_h = len(title_lines) * line_h + (len(title_lines) - 1) * spacing
    ty      = int(HEIGHT * 0.44) - block_h // 2 + _y_delta

    for line in title_lines:
        lh = _draw_line_centered(draw, line, font_title, title_color, ty,
                                 tracking=0.01,
                                 stroke_width=2, stroke_fill=(0, 0, 0, 160))
        ty += lh + spacing

    # ── Subtitle — small, dimmed, below hook ───────────────────────────────
    subtitle = content.get("subtitle", "")
    if subtitle:
        sub_size  = 26
        sub_color = (255, 255, 255, 90) if layout not in ("tarot",) else (GOLD[0], GOLD[1], GOLD[2], 100)
        font_sub  = _load_font("Montserrat", "Regular", sub_size)
        bbox_sub  = draw.textbbox((0, 0), subtitle, font=font_sub)
        draw.text(((WIDTH - (bbox_sub[2] - bbox_sub[0])) // 2, ty + spacing + 8),
                  subtitle, font=font_sub, fill=sub_color)

    # ── Bottom decoration per layout ───────────────────────────────────────
    if layout in ("oracle", "silhouette"):
        _draw_gold_line(draw, 1752, length=180, thickness=2)
        font_hint = _load_font("Montserrat", "Regular", 24)
        bbox = draw.textbbox((0, 0), "Glissez →", font=font_hint)
        draw.text(((WIDTH - (bbox[2] - bbox[0])) // 2, 1800), "Glissez →",
                  font=font_hint, fill=(GOLD[0], GOLD[1], GOLD[2], 160))
    elif layout in ("mystique", "lune"):
        _draw_diamond(draw, WIDTH // 2, 1820, 12, alpha=120)
    elif layout == "tarot":
        _draw_gold_line(draw, 1752, length=240, thickness=2)
        _draw_diamond(draw, WIDTH // 2, 1800, 9, alpha=200)
    elif layout == "cosmique":
        _draw_gold_line(draw, 1752, length=140, thickness=2)
    # minimal: clean

    img.convert("RGB").save(filepath, format="PNG")
    logger.info("[render] 01_cover.png ✓")


def _render_message(content: dict, filepath: str, layout: str = "oracle",
                    seed_offset: int = 0) -> None:
    img  = _make_base(seed=20 + seed_offset, layout=layout)
    draw = ImageDraw.Draw(img)
    _y_delta = [-25, 0, 25][seed_offset % 3]

    # ── Title — Montserrat Bold, level B hierarchy ─────────────────────────
    if layout in ("mystique", "silhouette", "lune"):
        title_color = CREAM
        body_style  = "LightItalic"
        body_color  = (CREAM[0], CREAM[1], CREAM[2], 220)
    elif layout == "tarot":
        title_color = GOLD_BRIGHT
        body_style  = "Regular"
        body_color  = CREAM
    elif layout == "cosmique":
        title_color = SILVER_BRIGHT
        body_style  = "Regular"
        body_color  = (SILVER[0], SILVER[1], SILVER[2], 220)
    else:
        title_color = WHITE
        body_style  = "Regular"
        body_color  = CREAM

    font_title   = _load_font("Montserrat", "Bold", 64)
    title        = content.get("title", "")
    title_lines  = _wrap_text_balanced(title, font_title, WIDTH - 120, draw, max_lines=2)
    title_bottom = 620 + _y_delta
    for tl in title_lines:
        lh = _draw_line_centered(draw, tl, font_title, title_color, title_bottom,
                                 stroke_width=2, stroke_fill=(0, 0, 0, 160))
        title_bottom += lh + 18

    # ── Body — Montserrat Regular, generous line spacing ──────────────────
    body_size = 48 if layout == "minimal" else 50
    font_body = _load_font("Montserrat", body_style, body_size)
    body      = content.get("body", "")
    body_y    = max(title_bottom + 64, 830)
    _draw_centered_text(draw, body, font_body, body_color, body_y,
                        max_width=860, line_spacing=36, max_lines=4)

    if layout in ("oracle", "silhouette"):
        _draw_gold_line(draw, 1750, length=200, thickness=4)
    elif layout == "minimal":
        _draw_gold_line(draw, 1750, length=120, thickness=2)
    elif layout == "tarot":
        _draw_gold_line(draw, 1748, length=260, thickness=3)
    elif layout == "cosmique":
        _draw_gold_line(draw, 1750, length=160, thickness=2)
    else:  # mystique, lune
        _draw_diamond(draw, WIDTH // 2, 1790, 12, alpha=150)

    img.convert("RGB").save(filepath, format="PNG")
    logger.info("[render] 02_message.png ✓")


def _render_revelation(content: dict, filepath: str, layout: str = "oracle",
                       seed_offset: int = 0) -> None:
    sc   = None if layout != "minimal" else 14
    img  = _make_base(seed=30 + seed_offset, star_count=sc, layout=layout)
    draw = ImageDraw.Draw(img)
    cx   = WIDTH // 2
    _y_delta = [-20, 0, 20][seed_offset % 3]
    text = content.get("text", content.get("title", ""))

    # ── Revelation — Oswald SemiBold, adaptive size, balanced ─────────────
    # Echoes hook font (Oswald) for emotional callback, SemiBold = clean/minimal.
    reveal_max_w = WIDTH - 100

    if layout == "oracle":
        _draw_diamond(draw, cx, 780, 22, alpha=220)
        y_start = 838
    elif layout == "minimal":
        y_start = None
    elif layout == "tarot":
        _draw_diamond(draw, cx, 760, 26, alpha=240)
        y_start = 828
    elif layout in ("lune", "silhouette"):
        _draw_diamond(draw, cx, 758, 18, alpha=150)
        y_start = 818
    elif layout == "cosmique":
        for dx in (-52, 0, 52):
            _draw_diamond(draw, cx + dx, 740, 16)
        y_start = 808
    else:  # mystique
        for dx in (-44, 0, 44):
            _draw_diamond(draw, cx + dx, 748, 14)
        y_start = 818

    font = _pick_reveal_size(text, draw, reveal_max_w)
    lines = _wrap_text_balanced(text, font, reveal_max_w, draw, max_lines=2)

    _bb     = draw.textbbox((0, 0), "Ag", font=font)
    line_h  = _bb[3] - _bb[1]
    spacing = max(8, int(line_h * 0.12))
    block_h = len(lines) * line_h + (len(lines) - 1) * spacing
    y       = max((y_start or 820) + _y_delta, (HEIGHT - block_h) // 2)

    if layout in ("minimal", "cosmique"):
        text_color = WHITE
    elif layout == "tarot":
        text_color = GOLD_BRIGHT
    else:
        text_color = CREAM

    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        draw.text(((WIDTH - (bbox[2] - bbox[0])) // 2, y), line, font=font,
                  fill=text_color, stroke_width=1, stroke_fill=(0, 0, 0, 120))
        y += (bbox[3] - bbox[1]) + spacing

    img.convert("RGB").save(filepath, format="PNG")
    logger.info("[render] 03_revelation.png ✓")


def _render_cta(content: dict, filepath: str, layout: str = "oracle",
                seed_offset: int = 0) -> None:
    img  = _make_base(seed=6 + seed_offset, layout=layout)
    draw = ImageDraw.Draw(img)
    _y_delta = [-20, 0, 20][seed_offset % 3]

    if layout in ("mystique", "silhouette"):
        _draw_diamond(draw, WIDTH // 2, 676 + _y_delta, 26)
        title_y = 756 + _y_delta
    elif layout == "tarot":
        _draw_diamond(draw, WIDTH // 2, 660 + _y_delta, 30, alpha=240)
        title_y = 750 + _y_delta
    elif layout == "cosmique":
        for dx in (-50, 0, 50):
            _draw_diamond(draw, WIDTH // 2 + dx, 660 + _y_delta, 16)
        title_y = 740 + _y_delta
    else:
        title_y = 736 + _y_delta

    # Title color per layout
    if layout == "tarot":
        title_color = GOLD_BRIGHT
    elif layout in ("lune", "cosmique"):
        title_color = SILVER_BRIGHT
    else:
        title_color = WHITE

    # ── CTA title — Montserrat SemiBold, level D (discreet/elegant) ────────
    font_title  = _load_font("Montserrat", "SemiBold", 54)
    title       = content.get("title", "")
    title_lines = _wrap_text_balanced(title, font_title, WIDTH - 100, draw, max_lines=2)
    ty = title_y
    for tl in title_lines:
        lh = _draw_line_centered(draw, tl, font_title, title_color, ty,
                                 stroke_width=1, stroke_fill=(0, 0, 0, 140))
        ty += lh + 16
    title_bottom = ty

    # ── Separator ──────────────────────────────────────────────────────────
    if layout == "minimal":
        line_len, line_thick = 100, 1
    elif layout == "tarot":
        line_len, line_thick = 240, 2
    else:
        line_len, line_thick = 160, 2
    _draw_gold_line(draw, title_bottom + 36, length=line_len, thickness=line_thick)

    # ── CTA action text — Montserrat Regular, gold, elegant ───────────────
    cta_text = content.get("cta", "Lien en bio").replace("🔗", "").strip()
    if cta_text:
        cta_col  = GOLD_BRIGHT if layout == "tarot" else GOLD
        font_cta = _load_font("Montserrat", "Regular", 42)
        _draw_centered_text(
            draw, cta_text, font_cta, cta_col, title_bottom + 92,
            max_width=WIDTH - 120, line_spacing=12,
        )

    # ── Watermark ──────────────────────────────────────────────────────────
    font_wm  = _load_font("Montserrat", "Regular", 22)
    wm_color = (GOLD[0], GOLD[1], GOLD[2], 110)
    bbox = draw.textbbox((0, 0), "Auryel", font=font_wm)
    draw.text(((WIDTH - (bbox[2] - bbox[0])) // 2, 1826), "Auryel", font=font_wm, fill=wm_color)

    img.convert("RGB").save(filepath, format="PNG")
    logger.info("[render] 04_cta.png ✓")


# ---------------------------------------------------------------------------
# WhatsApp slide renderer
# ---------------------------------------------------------------------------

def _draw_seen_ticks(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    """Double checkmark teal (WhatsApp seen)."""
    for dx in (0, 10):
        draw.line([(x + dx, y + 7), (x + dx + 8, y + 13), (x + dx + 16, y + 3)],
                  fill=_WA_SEEN_C, width=2)


def _draw_gray_ticks(draw: ImageDraw.ImageDraw, x: int, y: int) -> None:
    """Double checkmark gray (WhatsApp delivered, not yet seen)."""
    for dx in (0, 10):
        draw.line([(x + dx, y + 7), (x + dx + 8, y + 13), (x + dx + 16, y + 3)],
                  fill=_WA_TIME_C, width=2)


def _render_whatsapp(content: dict, filepath: str, layout: str = "mystique",
                     seed_offset: int = 0) -> None:
    img  = Image.new("RGBA", (WIDTH, HEIGHT), _WA_BG)
    draw = ImageDraw.Draw(img)

    _TIMES   = ["23:14", "23:15", "23:15", "23:16"]
    TAIL_SZ  = 14
    MARGIN   = 56
    RADIUS   = 22

    # ── Header ───────────────────────────────────────────────────────────────
    draw.rectangle([0, 0, WIDTH, 214], fill=_WA_HEADER_BG)

    av_cx, av_cy, av_r = 88, 106, 52
    draw.ellipse([av_cx - av_r, av_cy - av_r, av_cx + av_r, av_cy + av_r],
                 fill=_WA_AVATAR_BG)
    font_av = _load_font("Montserrat", "Bold", 44)
    bb = draw.textbbox((0, 0), "A", font=font_av)
    draw.text((av_cx - (bb[2] - bb[0]) // 2, av_cy - (bb[3] - bb[1]) // 2 - 2),
              "A", font=font_av, fill=(245, 220, 255, 240))

    # Green online dot on avatar
    dot_cx = av_cx + int(av_r * 0.70)
    dot_cy = av_cy + int(av_r * 0.70)
    draw.ellipse([dot_cx - 12, dot_cy - 12, dot_cx + 12, dot_cy + 12], fill=_WA_BG)
    draw.ellipse([dot_cx - 9,  dot_cy - 9,  dot_cx + 9,  dot_cy + 9],  fill=(37, 211, 102))

    font_name = _load_font("Montserrat", "SemiBold", 40)
    draw.text((166, 52), "Auryel", font=font_name, fill=_WA_NAME_C)
    font_status = _load_font("Montserrat", "Regular", 27)
    draw.text((166, 110), "En ligne", font=font_status, fill=_WA_TIME_C)
    draw.rectangle([0, 214, WIDTH, 215], fill=(255, 255, 255, 18))

    # ── "Aujourd'hui" date pill ───────────────────────────────────────────────
    date_txt  = "Aujourd'hui"
    font_date = _load_font("Montserrat", "Regular", 25)
    bb        = draw.textbbox((0, 0), date_txt, font=font_date)
    dw, dh    = bb[2] - bb[0] + 52, 44
    date_y    = 248
    dpx       = (WIDTH - dw) // 2
    draw.rounded_rectangle([dpx, date_y, dpx + dw, date_y + dh], radius=22, fill=_WA_DATE_BG)
    draw.text((dpx + 26, date_y + 10), date_txt, font=font_date, fill=_WA_DATE_C)

    # ── Message layout setup ──────────────────────────────────────────────────
    messages     = content.get("messages", [])[:4]
    font_msg     = _load_font("Montserrat", "Regular", 42)
    font_time    = _load_font("Montserrat", "Regular", 24)
    BUBBLE_MAX_W = 820
    PAD_X, PAD_Y = 30, 24
    LINE_H       = 58
    GAP          = 20

    last_user_idx   = max((i for i, m in enumerate(messages) if m.get("from") == "user"),   default=-1)
    last_auryel_idx = max((i for i, m in enumerate(messages) if m.get("from") != "user"),   default=-1)

    y_cur          = date_y + dh + 48
    bubble_bottoms: list[int] = []

    for mi, msg in enumerate(messages):
        sender    = msg.get("from", "user")
        text      = msg.get("text", "")
        is_user   = sender == "user"
        timestamp = _TIMES[min(mi, len(_TIMES) - 1)]

        lines: list[str] = []
        for raw in text.split("\n"):
            wrapped = _wrap_text(raw, font_msg, BUBBLE_MAX_W - PAD_X * 2, draw)
            lines.extend(wrapped if wrapped else [""])

        max_line_w = max((draw.textbbox((0, 0), l, font=font_msg)[2] for l in lines), default=80)
        time_w     = draw.textbbox((0, 0), timestamp, font=font_time)[2]
        tick_w     = 40 if is_user else 0
        bubble_w   = min(BUBBLE_MAX_W, max(max_line_w + PAD_X * 2 + 10, time_w + tick_w + PAD_X * 2 + 20))
        bubble_h   = len(lines) * LINE_H + PAD_Y * 2 + 34

        bx     = WIDTH - bubble_w - MARGIN if is_user else MARGIN
        by     = y_cur
        fill_c = _WA_BUBBLE_USR if is_user else _WA_BUBBLE_AUR

        # Subtle notification glow on last Auryel bubble
        if mi == last_auryel_idx and not is_user:
            glow = Image.new("RGBA", (WIDTH, HEIGHT), (0, 0, 0, 0))
            gd   = ImageDraw.Draw(glow)
            for exp, alpha in [(22, 4), (13, 9), (5, 15)]:
                gd.rounded_rectangle(
                    [bx - exp, by - exp, bx + bubble_w + exp, by + bubble_h + exp],
                    radius=RADIUS + exp // 2,
                    fill=(_WA_SEEN_C[0], _WA_SEEN_C[1], _WA_SEEN_C[2], alpha),
                )
            img.alpha_composite(glow)
            draw = ImageDraw.Draw(img)

        # Bubble body
        draw.rounded_rectangle([bx, by, bx + bubble_w, by + bubble_h], radius=RADIUS, fill=fill_c)

        # Bubble tail (triangle at top outer corner)
        ty0 = by + RADIUS
        if is_user:
            tx = bx + bubble_w
            draw.polygon([(tx - 2, ty0), (tx + TAIL_SZ, ty0 + TAIL_SZ),
                           (tx - 2, ty0 + TAIL_SZ * 2)], fill=fill_c)
        else:
            tx = bx
            draw.polygon([(tx + 2, ty0), (tx - TAIL_SZ, ty0 + TAIL_SZ),
                           (tx + 2, ty0 + TAIL_SZ * 2)], fill=fill_c)

        # Message text
        ty = by + PAD_Y
        for line in lines:
            draw.text((bx + PAD_X, ty), line, font=font_msg, fill=_WA_TEXT)
            ty += LINE_H

        # Timestamp
        t_x = bx + bubble_w - time_w - PAD_X
        draw.text((t_x, by + bubble_h - PAD_Y - 8), timestamp, font=font_time, fill=_WA_TIME_C)

        # Ticks: gray (delivered) on all user messages, teal (seen) on last only
        if is_user:
            tick_x = t_x + time_w + 6
            tick_y = by + bubble_h - PAD_Y - 8
            if mi == last_user_idx:
                _draw_seen_ticks(draw, tick_x, tick_y)
            else:
                _draw_gray_ticks(draw, tick_x, tick_y)

        bubble_bottoms.append(by + bubble_h)
        y_cur += bubble_h + GAP

    # ── "Vu" label right-aligned below last message (if last is user) ─────────
    if messages and messages[-1].get("from") == "user" and bubble_bottoms:
        font_vu = _load_font("Montserrat", "Regular", 22)
        vu_bb   = draw.textbbox((0, 0), "Vu", font=font_vu)
        vu_x    = WIDTH - MARGIN - (vu_bb[2] - vu_bb[0])
        draw.text((vu_x, bubble_bottoms[-1] + 6), "Vu", font=font_vu,
                  fill=(_WA_SEEN_C[0], _WA_SEEN_C[1], _WA_SEEN_C[2], 200))

    # ── "Auryel écrit..." typing indicator (only if there's space) ──────────────
    typing_y = HEIGHT - 216
    if y_cur + 60 < typing_y:
        font_typing = _load_font("Montserrat", "Regular", 30)
        typing_text = "Auryel écrit..."
        tb          = draw.textbbox((0, 0), typing_text, font=font_typing)
        t_pill_w    = tb[2] - tb[0] + 40
        t_pill_h    = 50
        draw.rounded_rectangle([MARGIN, typing_y, MARGIN + t_pill_w, typing_y + t_pill_h],
                                radius=25, fill=_WA_BUBBLE_AUR)
        draw.text((MARGIN + 20, typing_y + 10), typing_text, font=font_typing,
                  fill=(_WA_TIME_C[0], _WA_TIME_C[1], _WA_TIME_C[2], 200))

    # ── Input bar ─────────────────────────────────────────────────────────────
    bar_y = HEIGHT - 140
    draw.rectangle([0, bar_y, WIDTH, HEIGHT], fill=_WA_HEADER_BG)
    draw.rectangle([0, bar_y, WIDTH, bar_y + 1], fill=(255, 255, 255, 18))
    draw.rounded_rectangle([68, bar_y + 22, WIDTH - 68, HEIGHT - 28], radius=40, fill=_WA_BG)
    font_inp = _load_font("Montserrat", "Regular", 30)
    draw.text((116, bar_y + 44), "Message...", font=font_inp, fill=(76, 96, 108))

    # ── Watermark ─────────────────────────────────────────────────────────────
    font_wm  = _load_font("Montserrat", "Regular", 22)
    wm_color = (_WA_NAME_C[0], _WA_NAME_C[1], _WA_NAME_C[2], 90)
    bb = draw.textbbox((0, 0), "Auryel", font=font_wm)
    draw.text(((WIDTH - (bb[2] - bb[0])) // 2, bar_y - 44),
              "Auryel", font=font_wm, fill=wm_color)

    img.convert("RGB").save(filepath, format="PNG")
    logger.info("[render] 04_whatsapp.png ✓")


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
    Renders PNG slides + preview_sheet.png to output_dir.
    Supports 4-slide (matin/midi) and 5-slide (soir with WhatsApp) carousels.
    Layout read from content["layout"]. _seed_offset provides daily visual variation.
    Returns list of all rendered paths (slides + preview).
    """
    out    = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    layout      = content.get("layout", "oracle")
    seed_offset = content.get("_seed_offset", 0)
    slides      = content.get("slides", [])

    # File naming by slide count
    if len(slides) == 5:
        file_names = [
            "01_cover.png", "02_content.png", "03_revelation.png",
            "04_whatsapp.png", "05_cta.png",
        ]
    else:
        file_names = ["01_cover.png", "02_content_1.png", "03_content_2.png", "04_cta.png"]

    if len(slides) not in (4, 5):
        logger.warning(f"[render] Expected 4 or 5 slides, got {len(slides)}")

    slide_files: list[str] = []

    for idx, slide in enumerate(slides[:len(file_names)]):
        slide_type = slide.get("type", "")
        filepath   = str(out / file_names[idx])

        if slide_type in ("hook", "cover"):
            _render_cover(slide, filepath, layout, seed_offset=seed_offset)
        elif slide_type in ("message", "content"):
            _render_message(slide, filepath, layout, seed_offset=seed_offset)
        elif slide_type == "revelation":
            _render_revelation(slide, filepath, layout, seed_offset=seed_offset)
        elif slide_type == "whatsapp":
            _render_whatsapp(slide, filepath, layout, seed_offset=seed_offset)
        elif slide_type == "cta":
            _render_cta(slide, filepath, layout, seed_offset=seed_offset)
        else:
            logger.warning(f"[render] Unknown slide type '{slide_type}' at index {idx}, skipping.")
            continue

        slide_files.append(filepath)

    preview = render_preview_sheet(slide_files, str(out))
    return slide_files + [preview]
