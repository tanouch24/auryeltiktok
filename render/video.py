"""
render/video.py — Assemble PNG slides en MP4 1080x1920 TikTok.

Pacing différencié par série :

  MATIN  (4 slides) — dynamique, scroll-friendly          ~8.1s
    Cover   : 2.0s  zoom 12%  pan fort    → hook < 1s
    Content : 2.5s  zoom  6%  pan subtil
    Reveal  : 2.5s  zoom  8%  pan moyen
    CTA     : 2.0s  zoom  4%  statique

  MIDI   (4 slides) — contemplatif, lecture de verset    ~10.1s
    Cover   : 2.5s  zoom  8%  pan doux    → psaume
    Content : 3.0s  zoom  5%  pan minimal → verset — temps de lecture
    Reveal  : 3.0s  zoom  6%  pan doux    → révélation calme
    CTA     : 2.5s  zoom  3%  statique

  SOIR   (5 slides) — immersif, cinématographique        ~14.3s
    Cover       : 2.5s  zoom 12%  pan fort    → hook émotionnel
    Content     : 3.0s  zoom  6%  pan subtil  → tension / respiration
    Révélation  : 2.5s  zoom  8%  pan moyen   → pause dramatique
    WhatsApp    : 5.0s  zoom  2%  statique    → récompense émotionnelle
    CTA         : 2.5s  zoom  3%  statique    → contemplatif

  Crossfade : 0.3s (toutes séries)
"""

import json as _json
from pathlib import Path

import numpy as np
from PIL import Image

FPS           = 25
FADE_DURATION = 0.3

# ── Per-slide config: (filename, duration_s, zoom_factor, pan_drift, pan_direction)
# pan_drift : fraction de la plage de déplacement utilisée (Ken Burns H)
# pan_direction : +1 gauche→droite, -1 droite→gauche, 0 centre fixe

_SLIDE_CONFIGS_4_MATIN = [
    ("01_cover.png",     2.0, 0.12, 0.06,  1),   # hook — impact immédiat
    ("02_content_1.png", 2.5, 0.06, 0.02, -1),   # contenu — fluide
    ("03_content_2.png", 2.5, 0.08, 0.03,  1),   # révélation — élan
    ("04_cta.png",       2.0, 0.04, 0.00,  1),   # CTA — rapide
]

_SLIDE_CONFIGS_4_MIDI = [
    ("01_cover.png",     2.5, 0.08, 0.04,  1),   # psaume — plus doux
    ("02_content_1.png", 3.0, 0.05, 0.02, -1),   # verset — temps de lecture
    ("03_content_2.png", 3.0, 0.06, 0.02,  1),   # révélation — calme
    ("04_cta.png",       2.5, 0.03, 0.00,  1),   # CTA — contemplatif
]

_SLIDE_CONFIGS_5 = [
    ("01_cover.png",      2.5, 0.12, 0.06,  1),   # hook — doit accrocher
    ("02_content.png",    3.0, 0.06, 0.02, -1),   # tension — respiration émotionnelle
    ("03_revelation.png", 2.5, 0.08, 0.03,  1),   # tirage — pause dramatique
    ("04_whatsapp.png",   5.0, 0.02, 0.00,  0),   # WhatsApp — récompense émotionnelle
    ("05_cta.png",        2.5, 0.03, 0.00,  1),   # CTA — contemplatif
]

# Legacy aliases kept for external callers
_SLIDE_CONFIGS_4 = _SLIDE_CONFIGS_4_MATIN
_SLIDE_CONFIGS   = _SLIDE_CONFIGS_4_MATIN


def _require_moviepy():
    try:
        import moviepy.editor  # noqa: F401
    except ImportError:
        raise ImportError(
            "moviepy est requis pour l'export vidéo.\n"
            "  Installation : pip install 'moviepy>=1.0.3,<2.0'\n"
            "  ffmpeg requis : brew install ffmpeg  (macOS)\n"
            "                  apt install ffmpeg   (Linux)"
        )


def _detect_moment(slide_dir: Path) -> str:
    """Read content.json to return 'matin', 'midi', or 'soir'."""
    try:
        with open(slide_dir / "content.json", encoding="utf-8") as f:
            return _json.load(f).get("moment", "matin")
    except Exception:
        return "matin"


def _make_zoom_pan_clip(img_path: str, duration: float, fps: int,
                        zoom: float, pan_drift: float, pan_dir: int):
    """
    VideoClip avec zoom progressif + micro-dérive horizontale (Ken Burns dynamique).
    zoom      : facteur de zoom final (ex: 0.12 → +12% sur la durée du clip)
    pan_drift : fraction de la plage de déplacement utilisée (0 = centre fixe)
    pan_dir   : +1 / -1 pour alterner la direction du pan entre slides
    """
    from moviepy.editor import VideoClip

    img = Image.open(img_path).convert("RGB")
    w, h = img.size  # 1080 × 1920

    def make_frame(t: float):
        progress = t / duration

        # Zoom progressif
        scale = 1.0 + zoom * progress
        new_w = max(w + 2, int(w * scale))
        new_h = max(h + 2, int(h * scale))
        resized = img.resize((new_w, new_h), Image.LANCZOS)

        # Plage disponible pour le crop
        x_range = new_w - w
        y_range = new_h - h

        # Pan horizontal : dérive depuis le centre
        pan_offset = x_range * pan_drift * progress * pan_dir
        x_center   = x_range * 0.5
        x_off      = int(max(0, min(x_range, x_center + pan_offset)))
        y_off      = int(y_range * 0.5)

        return np.array(resized.crop((x_off, y_off, x_off + w, y_off + h)))

    return VideoClip(make_frame, duration=duration).set_fps(fps)


def render_video(series_dir: str) -> str:
    """
    Assemble les slides PNG d'un dossier en vidéo 1080x1920 MP4 optimisée TikTok.
    Détecte la série depuis content.json pour appliquer le pacing adapté.
    Soir : ajoute un ping WhatsApp au début de la slide WhatsApp.
    Sortie : <series_dir>/video.mp4
    """
    _require_moviepy()
    from moviepy.editor import concatenate_videoclips, AudioFileClip

    slide_dir = Path(series_dir)
    is_soir   = (slide_dir / "04_whatsapp.png").exists()

    if is_soir:
        configs = _SLIDE_CONFIGS_5
    else:
        moment  = _detect_moment(slide_dir)
        configs = _SLIDE_CONFIGS_4_MIDI if moment == "midi" else _SLIDE_CONFIGS_4_MATIN

    missing = [str(slide_dir / cfg[0]) for cfg in configs
               if not (slide_dir / cfg[0]).exists()]
    if missing:
        raise FileNotFoundError(f"Slides manquantes pour l'export vidéo : {missing}")

    clips = []
    for i, (name, duration, zoom, pan, direction) in enumerate(configs):
        clip = _make_zoom_pan_clip(
            str(slide_dir / name), duration, FPS, zoom, pan, direction
        )
        if i > 0:
            clip = clip.crossfadein(FADE_DURATION)
        if i < len(configs) - 1:
            clip = clip.crossfadeout(FADE_DURATION)
        clips.append(clip)

    final    = concatenate_videoclips(clips, method="compose")
    out_path = slide_dir / "video.mp4"

    # Optional notification ping for soir (fires at start of WhatsApp slide)
    audio_clip = None
    if is_soir:
        try:
            from render.audio import generate_notification_wav
            ping_at   = sum(cfg[1] for cfg in _SLIDE_CONFIGS_5[:3]) - FADE_DURATION * 2
            wav_path  = str(slide_dir / "notification.wav")
            generate_notification_wav(final.duration, ping_at, wav_path)
            audio_clip = AudioFileClip(wav_path)
            final      = final.set_audio(audio_clip)
        except Exception:
            audio_clip = None

    final.write_videofile(
        str(out_path),
        fps=FPS,
        codec="libx264",
        audio=audio_clip is not None,
        verbose=False,
    )
    return str(out_path)
