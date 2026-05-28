from dotenv import load_dotenv
import argparse
import os
import json
import logging
import shutil
from datetime import datetime, timedelta
from pathlib import Path

from generators import motivation, midi, spirituality
from render.renderer import render_carousel
from render.video import render_video as _render_video

logging.basicConfig(level=logging.WARNING)

load_dotenv()


def get_output_dir() -> Path:
    """
    Return the output directory for today's run.
    Falls back to YYYY-MM-DD_HH-MM if the date folder already has content.
    """
    now   = datetime.now()
    today = now.strftime("%Y-%m-%d")
    base  = Path("output") / today

    def _has_content(d: Path) -> bool:
        return any(
            (d / s).exists() and any((d / s).iterdir())
            for s in ("matin", "midi", "soir")
        )

    if not base.exists() or not _has_content(base):
        return base

    for offset in range(60):
        total_min = now.minute + offset
        ts = now.replace(
            hour   = now.hour + total_min // 60,
            minute = total_min % 60,
            second = 0, microsecond = 0,
        )
        candidate = Path("output") / ts.strftime("%Y-%m-%d_%H-%M")
        if not candidate.exists() or not _has_content(candidate):
            return candidate

    return Path("output") / now.strftime("%Y-%m-%d_%H-%M-%S")


def _desktop_export(video_src: Path, moment: str, date_str: str) -> str:
    """
    Copy video.mp4 → ~/Desktop/AuryelTikTok/YYYY-MM-DD/moment.mp4.
    Adds HHhMM prefix on same-day collision. Returns dest path or "".
    """
    if not video_src.exists():
        return ""

    dest_dir = Path.home() / "Desktop" / "AuryelTikTok" / date_str
    dest_dir.mkdir(parents=True, exist_ok=True)

    dest = dest_dir / f"{moment}.mp4"
    if dest.exists():
        ts   = datetime.now().strftime("%Hh%M")
        dest = dest_dir / f"{ts}_{moment}.mp4"
    if dest.exists():
        ts   = datetime.now().strftime("%Hh%M_%S")
        dest = dest_dir / f"{ts}_{moment}.mp4"

    shutil.copy2(str(video_src), str(dest))
    return str(dest)


def run_series(moment: str, generator_fn, api_key: str, base_dir: Path,
               expected_slides: int = 4, date_override: str = "") -> tuple[dict, int]:
    """
    Generate content, render slides, export video, save content.json.
    Returns (content_dict, slide_count).
    """
    series_dir = base_dir / moment
    series_dir.mkdir(parents=True, exist_ok=True)

    content = generator_fn(api_key, date_override=date_override)

    slide_count = len(content.get("slides", []))
    if slide_count != expected_slides:
        raise ValueError(f"Expected {expected_slides} slides, got {slide_count}")

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
    png_count    = len([f for f in output_files if "preview_sheet" not in f])
    print(f"  ✓ {png_count} slides rendues + preview_sheet.png")

    with open(series_dir / "content.json", "w", encoding="utf-8") as f:
        json.dump(content, f, ensure_ascii=False, indent=2)
    print("  ✓ content.json sauvegardé")

    try:
        video_path = _render_video(str(series_dir))
        size_kb    = Path(video_path).stat().st_size // 1024
        print(f"  ✓ video.mp4 exporté ({size_kb} KB)")
    except ImportError as exc:
        print(f"  ⚠ Export vidéo ignoré : {exc}")
    except Exception as exc:
        print(f"  ⚠ Export vidéo échoué : {exc}")

    return content, png_count


_SERIES_CONFIG = [
    ("MATIN", "matin", "Guidance Matin",   "🌅", motivation.generate,   4),
    ("MIDI",  "midi",  "Psaume du jour",   "☀️", midi.generate,         4),
    ("SOIR",  "soir",  "Histoire du soir", "🌙", spirituality.generate, 5),
]


def _run_day(api_key: str, output_dir: Path, target_date: str) -> tuple[int, list[str]]:
    """Generate all 3 series for one day. Returns (slide_count, desktop_paths)."""
    total_images = 0
    desk_exports: list[str] = []

    for display_name, moment, default_topic, icon, generator_fn, exp_slides in _SERIES_CONFIG:
        print("⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻")
        try:
            content, png_count = run_series(
                moment, generator_fn, api_key, output_dir,
                expected_slides=exp_slides, date_override=target_date,
            )
            topic = content.get("serie", default_topic or display_name)
            print(f"\r{icon} Série {display_name} — {topic}", flush=True)
            total_images += png_count

            video_src = output_dir / moment / "video.mp4"
            desk_path = _desktop_export(video_src, moment, target_date)
            if desk_path:
                print(f"  📱 Bureau  → {Path(desk_path).name}")
                desk_exports.append(desk_path)

        except Exception as e:
            topic = default_topic or display_name
            print(f"{icon} Série {display_name} — {topic}")
            print("⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻⸻")
            print(f"  ✗ Erreur: {e}")
        print()

    return total_images, desk_exports


def main():
    parser = argparse.ArgumentParser(description="Auryel TikTok — génération de contenu")
    parser.add_argument(
        "--days", type=int, default=1, metavar="N",
        help="Nombre de jours à générer en continu (défaut: 1)",
    )
    args = parser.parse_args()
    days    = max(1, args.days)
    api_key = os.getenv("ANTHROPIC_API_KEY", "")

    start_date = datetime.now().strftime("%Y-%m-%d")
    end_date   = (datetime.now() + timedelta(days=days - 1)).strftime("%Y-%m-%d")

    print("╔══════════════════════════════════════╗")
    print("║    🔮 AURYEL — Génération TikTok    ║")
    print("╚══════════════════════════════════════╝")
    print()
    if days == 1:
        desk_base = Path.home() / "Desktop" / "AuryelTikTok" / start_date
        print(f"📅 Date    : {start_date}")
        print(f"🖥  Bureau  : {desk_base}")
        print(f"🎬 3 vidéos : Matin + Midi + Soir")
    else:
        print(f"📅 {days} jours   : {start_date} → {end_date}")
        print(f"🖥  Bureau  : {Path.home() / 'Desktop' / 'AuryelTikTok'}/")
        print(f"🎬 {days * 3} vidéos  : {days} × (Matin + Midi + Soir)")
    print()

    all_images: int       = 0
    all_exports: list[str] = []

    for day_idx in range(days):
        target_date = (datetime.now() + timedelta(days=day_idx)).strftime("%Y-%m-%d")

        if days == 1:
            output_dir = get_output_dir()
        else:
            output_dir = Path("output") / target_date
            print(f"{'═' * 44}")
            print(f"  📅 Jour {day_idx + 1}/{days} — {target_date}")
            print(f"{'═' * 44}")
            print()

        day_images, day_exports = _run_day(api_key, output_dir, target_date)
        all_images  += day_images
        all_exports.extend(day_exports)

        if days > 1 and day_exports:
            desk_day = Path.home() / "Desktop" / "AuryelTikTok" / target_date
            print(f"  ✅ {target_date} — {len(day_exports)} vidéo(s) → {desk_day}")
            print()

    # ── Summary ───────────────────────────────────────────────────────────────
    print("══════════════════════════════════════")
    print(f"✅ {all_images} slides — {days} jour(s) générés")
    if all_exports:
        print(f"📱 {len(all_exports)} vidéo(s) sur le Bureau")
        if days > 1:
            by_date: dict[str, list[str]] = {}
            for p in all_exports:
                d = Path(p).parent.name
                by_date.setdefault(d, []).append(Path(p).name)
            for d, names in sorted(by_date.items()):
                print(f"   {d}/ : {', '.join(names)}")
    print("══════════════════════════════════════")


if __name__ == "__main__":
    main()
