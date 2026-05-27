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

STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "used_psalms.json"
HOOKS_FILE = Path(__file__).resolve().parent.parent / "data" / "hooks.json"

FALLBACK = {
    "serie":  "Psaume du jour",
    "moment": "aprem",
    "layout": "oracle",
    "slides": [
        {
            "type":     "cover",
            "title":    "Ce verset t'est destiné aujourd'hui",
            "subtitle": "Psaume du jour",
        },
        {
            "type":  "content",
            "num":   1,
            "title": "Je ne manquerai de rien",
            "body":  "\"L'Éternel est mon berger.\"\nTu es guidé·e et protégé·e.\nLaisse-toi porter.",
        },
        {
            "type":  "content",
            "num":   2,
            "title": "Tu es accompagné·e",
            "body":  "Ce psaume t'accompagne exactement\nlà où tu en es aujourd'hui.",
        },
        {
            "type":  "cta",
            "title": "Reçois ton message du jour",
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
    layout        = pick_layout(f"aprem-{today}")
    forbidden     = get_forbidden_words()
    forbidden_str = ", ".join(forbidden) if forbidden else "aucun"

    used      = _load_used()
    available = [n for n in range(1, 151) if n not in used]
    if not available:
        used      = []
        available = list(range(1, 151))
    psalm_number = random.choice(available)

    try:
        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""Génère un carousel TikTok pour le Psaume {psalm_number} en JSON.

STRUCTURE RÉTENTION — exactement 4 slides :

SLIDE 1 — cover (STOP SCROLL) :
  title = accroche max 8 mots, JAMAIS "Psaume {psalm_number}", crée désir immédiat de lire
  Ex : "Ces mots ont été écrits pour toi" / "Ce que Dieu dit quand tu doutes"
  subtitle = "Psaume {psalm_number}"

SLIDE 2 — content num 1 (ÉMOTION) :
  title max 8 mots — phrase forte tirée du psaume
  body max 18 mots — 1 verset court entre guillemets + 1 phrase d'interprétation percutante

SLIDE 3 — content num 2 (CURIOSITÉ) :
  title max 8 mots
  body max 15 mots — application personnelle ultra-courte, ouvre une boucle

SLIDE 4 — cta (ACTION) :
  title max 10 mots — question directe

MOTS INTERDITS : {forbidden_str}
STYLE : ultra-court, chaque mot compte, tutoiement, sacré et intime, tout en français.

JSON uniquement :
{{
  "serie": "Psaume du jour",
  "moment": "aprem",
  "slides": [
    {{"type": "cover",   "title": "...", "subtitle": "Psaume {psalm_number}"}},
    {{"type": "content", "num": 1, "title": "...", "body": "..."}},
    {{"type": "content", "num": 2, "title": "...", "body": "..."}},
    {{"type": "cta",     "title": "...", "cta": "🔗 Lien en bio"}}
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
            logger.warning(f"[psalm] Expected 4 slides, got {len(slides)}, using fallback")
            return _apply_fallback(layout)

        if slides[3].get("type") == "cta":
            slides[3]["cta"] = "🔗 Lien en bio"

        content = enforce_limits(content)
        content["layout"]           = layout
        content["hook_score"]       = score_hook(slides[0].get("title", ""))
        content["read_time_seconds"]= estimate_read_time(slides)
        content["emotion_score"]    = emotion_score(slides)
        content["curiosity_score"]  = curiosity_score(slides)

        used.append(psalm_number)
        _save_used(used)
        _save_hook(slides[0].get("title", ""))
        save_word_history("aprem", slides)
        logger.info("[psalm] Generated via API")
        return content

    except Exception as e:
        logger.warning(f"[psalm] Using fallback (error: {e})")
        return _apply_fallback(layout)


def _apply_fallback(layout: str) -> dict:
    FALLBACK["layout"]           = layout
    FALLBACK["hook_score"]       = score_hook(FALLBACK["slides"][0]["title"])
    FALLBACK["read_time_seconds"]= estimate_read_time(FALLBACK["slides"])
    FALLBACK["emotion_score"]    = emotion_score(FALLBACK["slides"])
    FALLBACK["curiosity_score"]  = curiosity_score(FALLBACK["slides"])
    save_word_history("aprem", FALLBACK["slides"])
    return FALLBACK
