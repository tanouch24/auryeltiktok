import re
import json
import random
import logging
from pathlib import Path

import anthropic

logger = logging.getLogger(__name__)

STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "used_topics.json"

TOPICS = [
    "anges gardiens", "archanges", "numérologie", "tarot",
    "chakras", "lune", "signes du zodiaque", "rêves",
    "synchronicités", "protection spirituelle", "guérison",
    "abondance", "karma"
]

FALLBACK = {
    "serie": "Anges gardiens",
    "moment": "soir",
    "slides": [
        {"type": "cover", "title": "Ton ange gardien te parle", "subtitle": "Ce soir, écoute les signes"},
        {"type": "content", "num": 1, "icon": "👼", "title": "Il est toujours là", "body": "Ton ange gardien veille sur toi à chaque instant, même dans les moments de doute. Tu n'es jamais seul·e."},
        {"type": "content", "num": 2, "icon": "🔢", "title": "Les nombres répétés", "body": "Quand tu vois 11:11 ou 333, c'est un signe. Ton ange attire ton attention pour te dire que tu es sur le bon chemin."},
        {"type": "content", "num": 3, "icon": "🦋", "title": "Les signes du quotidien", "body": "Une plume, une pensée soudaine, une coïncidence... Ces petits miracles sont ses messages pour toi."},
        {"type": "transition", "title": "Quel signe as-tu reçu aujourd'hui ?", "body": "Prends un moment pour y réfléchir. Ton ange attend ta réponse."},
        {"type": "cta", "title": "Parle à ton guide spirituel ce soir", "cta1": "💬 Parler à mon guide", "cta2": "✨ auryel.fr"}
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
    available = [t for t in TOPICS if t not in used]
    if not available:
        used = []
        available = list(TOPICS)

    topic = random.choice(available)

    try:
        client = anthropic.Anthropic(api_key=api_key)

        prompt = f"""Génère un carousel spirituel du soir sur le thème "{topic}" en JSON.

Le carousel doit avoir exactement 6 slides dans cet ordre :
1. cover : title = titre accrocheur lié au thème "{topic}", subtitle = invitation mystérieuse pour ce soir
2. content num=1 : icon (un emoji), title (5-8 mots), body (2-3 phrases sur un signe/message/révélation lié à "{topic}")
3. content num=2 : icon (un emoji), title (5-8 mots), body (2-3 phrases sur un deuxième aspect de "{topic}")
4. content num=3 : icon (un emoji), title (5-8 mots), body (2-3 phrases sur un troisième aspect de "{topic}")
5. transition : title = question ou affirmation invitant à la réflexion, body = pensée de clôture pour la nuit
6. cta : title = invite à parler à son guide spirituel ce soir, cta1 = "💬 Parler à mon guide", cta2 = "✨ auryel.fr"

Ton : mystérieux, profond, engageant, jamais anxiogène. Tout le texte doit être en français.

Retourne uniquement du JSON valide avec cette structure :
{{
  "serie": "{topic.capitalize()}",
  "moment": "soir",
  "slides": [...]
}}"""

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = message.content[0].text
        content = _extract_json(raw)
        result = _validate(content, "spirituality")

        if result is not FALLBACK:
            used.append(topic)
            _save_used(used)
            logger.info("[spirituality] Generated via API")
        else:
            logger.warning("[spirituality] Using fallback (validation failed)")
        return result

    except Exception as e:
        logger.warning(f"[spirituality] Using fallback (error: {e})")
        return FALLBACK
