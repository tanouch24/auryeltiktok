import json
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

HOOKS_FILE = Path(__file__).resolve().parent.parent / "data" / "hooks.json"

FALLBACK = {
    "serie":  "Phrase de motivation spirituelle",
    "moment": "matin",
    "layout": "oracle",
    "slides": [
        {
            "type":     "cover",
            "title":    "Ce message n'est pas arrivé par hasard",
            "subtitle": "Motivation spirituelle",
        },
        {
            "type":  "content",
            "num":   1,
            "title": "Tu n'es pas oublié·e",
            "body":  "Même quand rien ne bouge,\nquelque chose travaille déjà\nen silence pour toi.",
        },
        {
            "type":  "content",
            "num":   2,
            "title": "La réponse arrive",
            "body":  "Observe ce qui revient dans ta vie.\nCe n'est pas un hasard.",
        },
        {
            "type":  "cta",
            "title": "Quel message t'attend ce matin ?",
            "cta":   "Lien en bio",
        },
    ],
}


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
        HOOKS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(HOOKS_FILE, "w", encoding="utf-8") as f:
            json.dump(used, f, ensure_ascii=False, indent=2)


def generate(api_key: str) -> dict:
    """Returns a content.json-compatible dict with exactly 4 slides."""
    today         = date.today().isoformat()
    layout        = pick_layout(f"matin-{today}")
    forbidden     = get_forbidden_words()
    forbidden_str = ", ".join(forbidden) if forbidden else "aucun"

    try:
        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""Génère un carousel TikTok de motivation spirituelle matinale en JSON.

PROGRESSION OBLIGATOIRE — exactement 4 slides :

SLIDE 1 — cover (INTRIGUE) :
  title = accroche élégante max 8 mots, crée une curiosité douce et immédiate
  INTERDIT ABSOLUMENT : "peur", "entités", "blocages", "manipulation", urgence artificielle
  INTERDIT : générique ("tu es fort", "tu peux le faire", "tu es capable")
  PRÉFÉRER : révélation intérieure, secret personnel, question suspendue
  Ex : "Ce que tu ignores encore sur toi" / "Il y a une raison que tu lis ceci"
  subtitle = "Motivation spirituelle"

SLIDE 2 — content num 1 (ÉMOTION) :
  title max 8 mots — espoir concret ou vérité intime, jamais banal
  body max 17 mots — 2–3 phrases courtes, chaque ligne touche directement, retours à la ligne

SLIDE 3 — content num 2 (RÉVÉLATION) :
  title max 8 mots
  body max 15 mots — vérité suspendue ou révélation douce, ne pas tout livrer

SLIDE 4 — cta (OUVERTURE) :
  title max 10 mots — invitation douce, pas d'urgence, ouverture

TON GLOBAL : élégant, mystique, apaisant, haut de gamme. Tutoiement. Aucune violence ou anxiété.
MOTS INTERDITS PARTOUT : {forbidden_str}, peur, entités, blocages, manipulation

JSON uniquement :
{{
  "serie": "Phrase de motivation spirituelle",
  "moment": "matin",
  "slides": [
    {{"type": "cover",   "title": "...", "subtitle": "Motivation spirituelle"}},
    {{"type": "content", "num": 1, "title": "...", "body": "..."}},
    {{"type": "content", "num": 2, "title": "...", "body": "..."}},
    {{"type": "cta",     "title": "...", "cta": "Continuer"}}
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
            logger.warning(f"[motivation] Expected 4 slides, got {len(slides)}, using fallback")
            return _apply_fallback(layout)

        if slides[3].get("type") == "cta":
            slides[3]["cta"] = "Continuer"

        content = enforce_limits(content)
        content["layout"]           = layout
        content["hook_score"]       = score_hook(slides[0].get("title", ""))
        content["read_time_seconds"]= estimate_read_time(slides)
        content["emotion_score"]    = emotion_score(slides)
        content["curiosity_score"]  = curiosity_score(slides)

        _save_hook(slides[0].get("title", ""))
        save_word_history("matin", slides)
        logger.info("[motivation] Generated via API")
        return content

    except Exception as e:
        logger.warning(f"[motivation] Using fallback (error: {e})")
        return _apply_fallback(layout)


def _apply_fallback(layout: str) -> dict:
    FALLBACK["layout"]           = layout
    FALLBACK["hook_score"]       = score_hook(FALLBACK["slides"][0]["title"])
    FALLBACK["read_time_seconds"]= estimate_read_time(FALLBACK["slides"])
    FALLBACK["emotion_score"]    = emotion_score(FALLBACK["slides"])
    FALLBACK["curiosity_score"]  = curiosity_score(FALLBACK["slides"])
    save_word_history("matin", FALLBACK["slides"])
    return FALLBACK
