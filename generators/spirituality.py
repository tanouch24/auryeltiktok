import json
import random
import logging
from datetime import date
from pathlib import Path

import anthropic

from generators.utils import (
    extract_json, score_hook, enforce_limits, estimate_read_time,
    emotion_score, curiosity_score,
    get_forbidden_words, save_word_history, pick_layout,
)

logger = logging.getLogger(__name__)

STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "used_topics.json"
HOOKS_FILE = Path(__file__).resolve().parent.parent / "data" / "hooks.json"

TOPICS = [
    "anges gardiens", "archanges", "numérologie", "tarot",
    "chakras", "lune", "signes du zodiaque", "rêves",
    "synchronicités", "protection spirituelle", "guérison",
    "abondance", "karma",
]

FALLBACK = {
    "serie":  "Anges gardiens",
    "moment": "soir",
    "layout": "oracle",
    "slides": [
        {
            "type":     "cover",
            "title":    "Lis ceci avant de dormir ce soir",
            "subtitle": "Anges gardiens",
        },
        {
            "type":  "content",
            "num":   1,
            "title": "Vous n'êtes jamais seul·e",
            "body":  "En ce moment même, votre ange veille.\nLes signes autour de vous\nne sont pas des coïncidences.",
        },
        {
            "type":  "content",
            "num":   2,
            "title": "Un message pour vous ce soir",
            "body":  "Quelqu'un dans l'invisible\npense encore à vous en ce moment.",
        },
        {
            "type":  "cta",
            "title": "Quel message vous est destiné ?",
            "cta":   "Lien en bio",
        },
    ],
}


def _load_used() -> list:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_used(used: list) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(used, f)


def _load_used_hooks() -> list:
    try:
        with open(HOOKS_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_hook(hook: str) -> None:
    used = _load_used_hooks()
    if hook not in used:
        used.append(hook)
        with open(HOOKS_FILE, "w", encoding="utf-8") as f:
            json.dump(used, f, ensure_ascii=False, indent=2)


def generate(api_key: str) -> dict:
    """Returns a content.json-compatible dict with exactly 4 slides."""
    today         = date.today().isoformat()
    layout        = pick_layout(f"soir-{today}")
    forbidden     = get_forbidden_words()
    forbidden_str = ", ".join(forbidden) if forbidden else "aucun"

    used      = _load_used()
    available = [t for t in TOPICS if t not in used]
    if not available:
        used      = []
        available = list(TOPICS)
    topic = random.choice(available)

    try:
        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""Génère un carousel TikTok de voyance spirituelle du soir sur "{topic}" en JSON.

PROGRESSION OBLIGATOIRE — exactement 4 slides :

SLIDE 1 — cover (INTRIGUE) :
  title = accroche mystérieuse et élégante max 8 mots, crée une intrigue douce et immédiate
  INTERDIT ABSOLUMENT : "peur", "entités", "blocages", "manipulation", urgence artificielle, menace
  INTERDIT : générique, "votre avenir", "un message pour vous"
  PRÉFÉRER : révélation intérieure, signe subtil, moment précis
  Ex : "Ce que {topic} révèle sur vous ce soir" / "Le signe que vous attendiez"
  subtitle = "{topic.capitalize()}"

SLIDE 2 — content num 1 (ÉMOTION) :
  title max 8 mots — révélation douce liée à {topic}
  body max 17 mots — phrases courtes, impact émotionnel bienveillant, vouvoiement, retours à la ligne

SLIDE 3 — content num 2 (RÉVÉLATION) :
  title max 8 mots
  body max 13 mots — vérité suspendue et apaisante, ouvre une boucle sans créer d'anxiété

SLIDE 4 — cta (OUVERTURE) :
  title max 10 mots — invitation élégante, pas d'urgence

TON GLOBAL : mystique, apaisant, haut de gamme, bienveillant. Vouvoiement. Tout en français.
MOTS INTERDITS PARTOUT : {forbidden_str}, peur, entités, blocages, manipulation

JSON uniquement :
{{
  "serie": "{topic.capitalize()}",
  "moment": "soir",
  "slides": [
    {{"type": "cover",   "title": "...", "subtitle": "{topic.capitalize()}"}},
    {{"type": "content", "num": 1, "title": "...", "body": "..."}},
    {{"type": "content", "num": 2, "title": "...", "body": "..."}},
    {{"type": "cta",     "title": "...", "cta": "Découvrir mon message"}}
  ]
}}"""

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=700,
            messages=[{"role": "user", "content": prompt}],
        )

        raw     = message.content[0].text
        content = extract_json(raw)

        slides = content.get("slides", [])
        if len(slides) != 4:
            logger.warning(f"[spirituality] Expected 4 slides, got {len(slides)}, using fallback")
            return _apply_fallback(layout)

        if slides[3].get("type") == "cta":
            slides[3]["cta"] = "Découvrir mon message"

        content = enforce_limits(content)
        content["layout"]           = layout
        content["hook_score"]       = score_hook(slides[0].get("title", ""))
        content["read_time_seconds"]= estimate_read_time(slides)
        content["emotion_score"]    = emotion_score(slides)
        content["curiosity_score"]  = curiosity_score(slides)

        used.append(topic)
        _save_used(used)
        _save_hook(slides[0].get("title", ""))
        save_word_history("soir", slides)
        logger.info("[spirituality] Generated via API")
        return content

    except Exception as e:
        logger.warning(f"[spirituality] Using fallback (error: {e})")
        return _apply_fallback(layout)


def _apply_fallback(layout: str) -> dict:
    FALLBACK["layout"]           = layout
    FALLBACK["hook_score"]       = score_hook(FALLBACK["slides"][0]["title"])
    FALLBACK["read_time_seconds"]= estimate_read_time(FALLBACK["slides"])
    FALLBACK["emotion_score"]    = emotion_score(FALLBACK["slides"])
    FALLBACK["curiosity_score"]  = curiosity_score(FALLBACK["slides"])
    save_word_history("soir", FALLBACK["slides"])
    return FALLBACK
