"""
generators/psalm.py — Série APREM : Choix / Interaction.
Le numéro tiré (1-150) devient le "chiffre choisi" dans le format TikTok interactif.
"""
import json
import random
import logging
from datetime import date
from pathlib import Path

import anthropic

from generators.utils import (
    extract_json, score_hook, enforce_limits, estimate_read_time,
    emotion_score, curiosity_score, validate_content,
    get_forbidden_words, save_word_history, pick_layout, pick_seed_offset,
)

logger = logging.getLogger(__name__)

STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "used_psalms.json"
HOOKS_FILE = Path(__file__).resolve().parent.parent / "data" / "hooks.json"

_CTA_TITLE = "Quel chiffre as-tu choisi ?"
_CTA_TEXT  = "Quel chiffre as-tu choisi ?"

# Choice hooks vary — not always "chiffre", sometimes "carte", "couleur", "symbole"
_CHOICE_TYPES = [
    ("chiffre", ["1", "2", "3"]),
    ("chiffre", ["4", "5", "6"]),
    ("chiffre", ["7", "8", "9"]),
    ("carte",   ["A", "B", "C"]),
    ("symbole", ["☽", "★", "♦"]),
]

FALLBACK = {
    "serie":  "Choix & Révélation",
    "moment": "aprem",
    "layout": "oracle",
    "slides": [
        {
            "type":     "cover",
            "title":    "Choisis un chiffre sans réfléchir.",
            "subtitle": "Ton choix révèle quelque chose",
        },
        {
            "type":  "content",
            "num":   1,
            "title": "Ton intuition a déjà choisi",
            "body":  "Le premier chiffre qui vient en tête.\nCe n'est jamais vraiment un hasard.",
        },
        {
            "type": "revelation",
            "text": "Ton choix dit quelque chose de toi.",
        },
        {
            "type":  "cta",
            "title": _CTA_TITLE,
            "cta":   _CTA_TEXT,
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
    layout        = pick_layout(f"aprem-{today}", category="choix")
    seed_offset   = pick_seed_offset(f"aprem-{today}")
    forbidden     = get_forbidden_words()
    forbidden_str = ", ".join(forbidden) if forbidden else "aucun"

    used      = _load_used()
    available = [n for n in range(1, 151) if n not in used]
    if not available:
        used      = []
        available = list(range(1, 151))
    reveal_number = random.choice(available)

    # Pick a choice type (chiffre / carte / symbole) for variety
    choice_type, choices = random.choice(_CHOICE_TYPES)
    choices_str = " / ".join(choices)

    prompt = f"""Génère un carousel TikTok interactif "Choix & Révélation" en JSON.

CONCEPT : L'utilisateur choisit un {choice_type} ({choices_str}) et découvre un message personnalisé.
FORMAT TikTok viral : hook d'interaction → build-up → révélation partielle → CTA commentaire.
Numéro de révélation du jour : {reveal_number} (utilise ce nombre dans la révélation si tu choisis les chiffres).

PROGRESSION OBLIGATOIRE — exactement 4 slides :

SLIDE 1 — cover (HOOK INTERACTIF) :
  type = "cover"
  title MAXIMUM 6 MOTS — invite à choisir, mystère
  EXEMPLES (varier les formulations) :
    "Choisis un {choice_type} sans réfléchir."
    "Lequel attire ton regard ?"
    "Ton choix révèle quelque chose."
    "Choisis. Ton intuition sait déjà."
    "Un {choice_type} va parler pour toi."
    "Le {choice_type} qui insiste. Lequel ?"
  subtitle = "Ton choix révèle quelque chose"
  INTERDIT : révélation, énergie, vibration, accusation, morale

SLIDE 2 — content (BUILD-UP / TENSION) :
  type = "content", num = 1
  title MAXIMUM 5 MOTS — renforce la curiosité sur le choix
  EXEMPLES title : "Ton intuition a déjà choisi" / "Ce choix n'est pas anodin" / "Quelque chose guide ta main"
  body MAXIMUM 15 MOTS — 2 lignes séparées par \\n
  Formule : ligne 1 = valider l'instinct / ligne 2 = créer attente sur la révélation
  EXEMPLES body :
    "Le premier {choice_type} qui vient en tête.\\nCe n'est jamais vraiment un hasard."
    "Chaque choix reflète quelque chose.\\nCe que tu portes en ce moment."
    "Ton instinct connaît déjà la réponse.\\nLa révélation confirme ce que tu ressens."
  Tutoiement, ton mystérieux, phrases courtes

SLIDE 3 — revelation (RÉVÉLATION PARTIELLE) :
  type = "revelation"
  text MAXIMUM 8 MOTS — annonce qu'il y a une révélation pour leur choix, sans tout dévoiler
  EXEMPLES :
    "Chaque {choice_type} a son message."
    "Le {choice_type} {reveal_number} a quelque chose à dire."
    "Ta révélation est en commentaire."
    "Ton choix t'a déjà répondu."
    "Ce {choice_type} ne ment pas."
  Phrase assertive, courte, qui donne envie de commenter

SLIDE 4 — cta :
  type = "cta"
  title = "{_CTA_TITLE}"
  cta = "{_CTA_TEXT}"

TON : mystérieux, interactif, engageant. Tutoiement. Tout en français.
INTERDIT partout : {forbidden_str}, révélation (le mot), énergie, vibration, âme, entités, destin

JSON uniquement :
{{
  "serie": "Choix & Révélation",
  "moment": "aprem",
  "slides": [
    {{"type": "cover",      "title": "...", "subtitle": "Ton choix révèle quelque chose"}},
    {{"type": "content",    "num": 1, "title": "...", "body": "...\\n..."}},
    {{"type": "revelation", "text": "..."}},
    {{"type": "cta",        "title": "{_CTA_TITLE}", "cta": "{_CTA_TEXT}"}}
  ]
}}"""

    try:
        client = anthropic.Anthropic(api_key=api_key)
        best = None

        for attempt in range(3):
            try:
                message = client.messages.create(
                    model="claude-haiku-4-5-20251001",
                    max_tokens=700,
                    messages=[{"role": "user", "content": prompt}],
                )
                content = extract_json(message.content[0].text)
            except Exception as exc:
                logger.warning(f"[psalm] attempt {attempt+1} parse error: {exc}")
                continue

            slides = content.get("slides", [])
            if len(slides) != 4:
                logger.warning(f"[psalm] attempt {attempt+1}: {len(slides)} slides")
                continue

            content = enforce_limits(content)
            slides  = content["slides"]

            if slides[3].get("type") == "cta":
                slides[3]["cta"]   = _CTA_TEXT
                slides[3]["title"] = _CTA_TITLE

            content["layout"]            = layout
            content["_seed_offset"]      = seed_offset
            content["hook_score"]        = score_hook(slides[0].get("title", ""))
            content["read_time_seconds"] = estimate_read_time(slides)
            content["emotion_score"]     = emotion_score(slides)
            content["curiosity_score"]   = curiosity_score(slides)

            errors = validate_content(content)
            if errors:
                logger.warning(f"[psalm] attempt {attempt+1} validation: {errors}")
                best = content
                continue

            best = content
            break

        if best is None:
            logger.warning("[psalm] all attempts failed, using fallback")
            return _apply_fallback(layout)

        used.append(reveal_number)
        _save_used(used)
        _save_hook(best["slides"][0].get("title", ""))
        save_word_history("aprem", best["slides"])
        logger.info("[psalm] Generated via API")
        return best

    except Exception as e:
        logger.warning(f"[psalm] Using fallback (error: {e})")
        return _apply_fallback(layout)


def _apply_fallback(layout: str) -> dict:
    FALLBACK["layout"]            = layout
    FALLBACK["hook_score"]        = score_hook(FALLBACK["slides"][0]["title"])
    FALLBACK["read_time_seconds"] = estimate_read_time(FALLBACK["slides"])
    FALLBACK["emotion_score"]     = emotion_score(FALLBACK["slides"])
    FALLBACK["curiosity_score"]   = curiosity_score(FALLBACK["slides"])
    save_word_history("aprem", FALLBACK["slides"])
    return FALLBACK
