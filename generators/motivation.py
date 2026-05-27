import re
import json
import logging

import anthropic

logger = logging.getLogger(__name__)

FALLBACK = {
    "serie": "Phrase de motivation spirituelle",
    "moment": "matin",
    "slides": [
        {"type": "cover", "title": "Tu es guidé·e", "subtitle": "Commence ta journée avec cette lumière"},
        {"type": "content", "num": 1, "icon": "✨", "title": "L'univers conspire pour toi", "body": "Chaque matin est une nouvelle invitation à avancer. Tu n'es jamais seul·e sur ce chemin."},
        {"type": "content", "num": 2, "icon": "🌙", "title": "Ta lumière est unique", "body": "Ce que tu apportes au monde ne peut venir que de toi. Fais confiance à ce que tu ressens."},
        {"type": "content", "num": 3, "icon": "💫", "title": "Chaque étape compte", "body": "Même les petits pas te rapprochent de là où tu dois aller. L'univers voit ton chemin entier."},
        {"type": "transition", "title": "Et si aujourd'hui était le jour ?", "body": "Le moment est maintenant. Tu es prêt·e."},
        {"type": "cta", "title": "Reçois un message personnalisé de ton guide", "cta1": "💬 Parler à mon guide", "cta2": "✨ auryel.fr"}
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


def generate(api_key: str) -> dict:
    """Returns a content.json-compatible dict with exactly 6 slides."""
    try:
        client = anthropic.Anthropic(api_key=api_key)

        prompt = """Génère un carousel de motivation spirituelle matinale en JSON.

Le carousel doit avoir exactement 6 slides dans cet ordre :
1. cover : titre = courte phrase inspirante (ex: "Tu es guidé·e"), subtitle = invitation douce
2. content num=1 : icon (un emoji), title (5-8 mots inspirants), body (2-3 phrases max, doux et inspirant)
3. content num=2 : icon (un emoji), title (5-8 mots inspirants), body (2-3 phrases max, doux et inspirant)
4. content num=3 : icon (un emoji), title (5-8 mots inspirants), body (2-3 phrases max, doux et inspirant)
5. transition : title = question ou affirmation réflexive, body = pensée de clôture douce
6. cta : title = invite l'utilisateur à contacter son guide, cta1 = "💬 Parler à mon guide", cta2 = "✨ auryel.fr"

Thème : motivation spirituelle matinale. Ton : doux, positif, inspirant. Jamais culpabilisant.
Tout le texte doit être en français.

Retourne uniquement du JSON valide avec cette structure :
{
  "serie": "Phrase de motivation spirituelle",
  "moment": "matin",
  "slides": [...]
}"""

        message = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}]
        )

        raw = message.content[0].text
        content = _extract_json(raw)
        result = _validate(content, "motivation")
        if result is not FALLBACK:
            logger.info("[motivation] Generated via API")
        else:
            logger.warning("[motivation] Using fallback (validation failed)")
        return result

    except Exception as e:
        logger.warning(f"[motivation] Using fallback (error: {e})")
        return FALLBACK
