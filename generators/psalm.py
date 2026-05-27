import re
import json
import random
import logging
from pathlib import Path

import anthropic

logger = logging.getLogger(__name__)

STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "used_psalms.json"

FALLBACK = {
    "serie": "Psaume du jour",
    "moment": "aprem",
    "slides": [
        {"type": "cover", "title": "Psaume 23", "subtitle": "Le Seigneur est mon berger"},
        {"type": "content", "num": 1, "icon": "🕊️", "title": "Je ne manquerai de rien", "body": "L'Éternel est mon berger. Il me conduit vers des eaux paisibles et restaure mon âme."},
        {"type": "content", "num": 2, "icon": "✨", "title": "Même dans la vallée", "body": "Même si je marche dans la vallée de l'ombre, je ne crains aucun mal. Tu es avec moi."},
        {"type": "content", "num": 3, "icon": "🌿", "title": "Ta bonté me suit", "body": "Certainement le bonheur et la grâce m'accompagneront tous les jours de ma vie."},
        {"type": "transition", "title": "Ce psaume t'est destiné aujourd'hui", "body": "Laisse ces mots résonner en toi. Tu es protégé·e."},
        {"type": "cta", "title": "Reçois ton message du jour", "cta1": "💬 Parler à mon guide", "cta2": "✨ auryel.fr"}
    ]
}


def _extract_json(text: str) -> dict:
    """Extract JSON from a Claude response that may have markdown fences."""
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        return json.loads(match.group(1))
    return json.loads(text.strip())


def _validate(content: dict, module_name: str) -> dict:
    slides = content.get("slides", [])
    if len(slides) != 6:
        logger.warning(f"[{module_name}] Invalid slide count ({len(slides)}), using fallback")
        return FALLBACK
    return content


def _load_used() -> list:
    try:
        with open(STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return []


def _save_used(used: list) -> None:
    STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(used, f)


def generate(api_key: str) -> dict:
    """Returns a content.json-compatible dict with exactly 6 slides."""
    used = _load_used()
    available = [n for n in range(1, 151) if n not in used]
    if not available:
        used = []
        available = list(range(1, 151))

    psalm_number = random.choice(available)

    try:
        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""Génère un carousel spirituel pour le Psaume {psalm_number} de la Bible en JSON.

Le carousel doit avoir exactement 6 slides dans cet ordre :
1. cover : title = "Psaume {psalm_number}", subtitle = le thème principal ou verset clé du psaume
2. content num=1 : icon (un emoji), title (5-8 mots), body (2-3 phrases sur le premier verset ou thème clé)
3. content num=2 : icon (un emoji), title (5-8 mots), body (2-3 phrases sur le deuxième verset ou thème clé)
4. content num=3 : icon (un emoji), title (5-8 mots), body (2-3 phrases sur le troisième verset ou thème clé)
5. transition : title = message central ou affirmation, body = pensée de clôture apaisante
6. cta : title = invite à recevoir son message du jour, cta1 = "💬 Parler à mon guide", cta2 = "✨ auryel.fr"

Ton : protecteur, apaisant, sacré, respectueux. Tout le texte doit être en français.

Retourne uniquement du JSON valide avec cette structure :
{{
  "serie": "Psaume du jour",
  "moment": "aprem",
  "slides": [...]
}}"""

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = message.content[0].text
        content = _extract_json(raw)
        result = _validate(content, "psalm")

        if result is not FALLBACK:
            used.append(psalm_number)
            _save_used(used)
            logger.info("[psalm] Generated via API")
        else:
            logger.warning("[psalm] Using fallback (validation failed)")
        return result

    except Exception as e:
        logger.warning(f"[psalm] Using fallback (error: {e})")
        return FALLBACK
