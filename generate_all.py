from dotenv import load_dotenv
import os
import json
import logging
from datetime import datetime
from pathlib import Path

from generators import motivation, psalm, spirituality
from render.renderer import render_carousel

logging.basicConfig(level=logging.WARNING)

load_dotenv()


def get_output_dir() -> Path:
    """
    Return the output directory for today's run.
    Falls back to YYYY-MM-DD_HH-MM if the date folder (or the timestamped one) already
    has non-empty series subdirs, to prevent overwriting earlier runs.
    """
    now = datetime.now()
    today = now.strftime("%Y-%m-%d")
    base = Path("output") / today

    def _has_content(d: Path) -> bool:
        series_dirs = [d / s for s in ("matin", "aprem", "soir")]
        return any(sd.exists() and any(sd.iterdir()) for sd in series_dirs)

    if not base.exists() or not _has_content(base):
        return base

    # Date folder occupied — use a timestamped fallback, incrementing minutes if needed
    for offset in range(60):
        ts = (now.replace(second=0, microsecond=0)
              .replace(minute=now.minute + offset)
              if now.minute + offset < 60
              else now.replace(hour=now.hour + (now.minute + offset) // 60,
                               minute=(now.minute + offset) % 60,
                               second=0, microsecond=0))
        candidate = Path("output") / ts.strftime("%Y-%m-%d_%H-%M")
        if not candidate.exists() or not _has_content(candidate):
            return candidate

    # Extreme edge case: all minutes occupied — append seconds
    return Path("output") / now.strftime("%Y-%m-%d_%H-%M-%S")


def run_series(moment: str, generator_fn, api_key: str, base_dir: Path) -> tuple[dict, int]:
    """
    Generate content, render slides, save content.json.
    Returns (content_dict, slide_count).
    Raises on any failure so caller can handle cleanly.
    """
    series_dir = base_dir / moment
    series_dir.mkdir(parents=True, exist_ok=True)

    content = generator_fn(api_key)

    slide_count = len(content.get("slides", []))
    if slide_count != 4:
        raise ValueError(f"Expected exactly 4 slides, got {slide_count}")

    hook       = content.get("slides", [{}])[0].get("title", "—")
    layout     = content.get("layout", "—")
    hook_sc    = content.get("hook_score", "—")
    emotion    = content.get("emotion_score", "—")
    curiosity  = content.get("curiosity_score", "—")
    conversion = content.get("conversion_score", "—")
    read_time  = content.get("read_time_seconds", "—")

    print(f"  ✓ Contenu généré")
    print(f"     Hook     : \"{hook}\"")
    print(f"     Layout   : {layout}")
    print(f"     Scores   : hook={hook_sc}  émotion={emotion}  curiosité={curiosity}  conv={conversion}")
    print(f"     Lecture  : {read_time}s")

    output_files = render_carousel(content, str(series_dir))
    png_count = len([f for f in output_files if "preview_sheet" not in f])
    print(f"  ✓ {png_count} slides rendues + preview_sheet.png")

    json_path = series_dir / "content.json"
    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)
    print("  ✓ content.json sauvegardé")

    return content, png_count


def main():
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    output_dir = get_output_dir()

    print("╔══════════════════════════════════════╗")
    print("║    🔮 AURYEL — Génération TikTok    ║")
    print("╚══════════════════════════════════════╝")
    print()
    print(f"📅 Date : {datetime.now().strftime('%Y-%m-%d')}")
    print(f"📁 Dossier : {output_dir}")
    print()

    series_config = [
        ("MATIN",      "matin", "Phrase de motivation spirituelle", "🌅", motivation.generate),
        ("APRÈS-MIDI", "aprem", "Psaume du jour",                   "☀️", psalm.generate),
        ("SOIR",       "soir",  None,                               "🌙", spirituality.generate),
    ]

    total_images = 0

    for display_name, moment, default_topic, icon, generator_fn in series_config:
        print("⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻")
        try:
            content, png_count = run_series(moment, generator_fn, api_key, output_dir)
            topic = content.get("serie", default_topic or display_name)
            # Print header after generation so dynamic topic (SOIR) is shown correctly
            print(f"\r{icon} Série {display_name} — {topic}", flush=True)
            total_images += png_count
        except Exception as e:
            topic = default_topic or display_name
            print(f"{icon} Série {display_name} — {topic}")
            print("⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻")
            print(f"  ✗ Erreur: {e}")
        print()

    print("══════════════════════════════════════")
    print(f"✅ {total_images} images générées → {output_dir}")
    print("══════════════════════════════════════")


if __name__ == "__main__":
    main()
