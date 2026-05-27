"""Shared utilities for all generators."""
import re
import json
import random
import hashlib
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
WORD_HISTORY_FILE = DATA_DIR / "word_history.json"

TRACKED_WORDS = ["univers", "guides", "énergie", "destin"]
FORBIDDEN_ACTIONS = ["découvrir maintenant", "lien en bio"]
DEFAULT_ACTIONS = [
    "Écris OUI en commentaire",
    "Commente SIGNE",
    "Réponds ÉTOILE",
    "Écris LUMIÈRE ci-dessous",
    "Écris OUI ci-dessous",
]


def extract_json(text: str) -> dict:
    match = re.search(r"```(?:json)?\s*([\s\S]+?)\s*```", text)
    if match:
        return json.loads(match.group(1))
    return json.loads(text.strip())


def score_hook(hook: str) -> int:
    """Score a hook 0-100 for TikTok engagement potential."""
    score = 40
    words = hook.split()
    hook_lower = hook.lower()
    wc = len(words)

    if 5 <= wc <= 8:
        score += 25
    elif 4 <= wc <= 10:
        score += 10
    elif wc > 10:
        score -= 15

    personal = {"tu", "toi", "ton", "ta", "tes", "vous", "votre", "vos"}
    if personal & set(hook_lower.split()):
        score += 15

    urgency = ["aujourd'hui", "ce soir", "ce matin", "maintenant",
               "bientôt", "avant de", "insiste", "insistent"]
    if any(w in hook_lower for w in urgency):
        score += 10

    mystery = ["secret", "caché", "cache", "révèle", "révélation",
               "message", "signe", "hasard", "veut", "attend", "arrive", "ceci"]
    if any(w in hook_lower for w in mystery):
        score += 10

    return min(100, max(0, score))


def emotion_score(slides: list) -> int:
    """0-100. Emotional resonance across slide text."""
    combined = " ".join(
        (s.get("title") or "") + " " + (s.get("body") or "") + " " + (s.get("text") or "")
        for s in slides
    ).lower()

    score = 30
    emotional_words = [
        "seul", "seule", "peur", "espoir", "cœur", "amour", "joie",
        "force", "courage", "douleur", "bonheur", "paix", "lumière",
        "blessé", "manque", "perdre", "gagner", "larme", "guéri",
    ]
    personal = ["tu ", "toi ", "ton ", "ta ", "tes ", "vous ", "votre ", "vos "]

    for w in emotional_words:
        if w in combined:
            score += 4
    for p in personal:
        if p in combined:
            score += 5

    return min(100, score)


def curiosity_score(slides: list) -> int:
    """0-100. Open-loop and curiosity-inducing language."""
    combined = " ".join(
        (s.get("title") or "") + " " + (s.get("body") or "") + " " + (s.get("text") or "")
        for s in slides
    ).lower()

    score = 20
    mystery = [
        "bientôt", "quelque chose", "secret", "cache", "révèle", "signe",
        "message", "hasard", "attend", "arrive", "comprendr", "savoir",
        "vérité", "caché", "révélation",
    ]

    if "?" in combined:
        score += 20
    for w in mystery:
        if w in combined:
            score += 5

    return min(100, score)


def conversion_score(slides: list) -> int:
    """0-100. Comment-command CTA strength."""
    cta = next((s for s in slides if s.get("type") == "cta"), {})
    combined = ((cta.get("title") or "") + " " + (cta.get("action") or "")).lower()

    score = 15
    commands = [
        "écri", "commente", "réponds", "dis ", "envoie",
        "oui", "signe", "étoile", "lumière", "tapez", "écrivez",
    ]

    for c in commands:
        if c in combined:
            score += 15

    for f in FORBIDDEN_ACTIONS:
        if f in combined:
            score -= 30

    return max(0, min(100, score))


def word_count(text: str) -> int:
    return len(text.split())


def truncate_words(text: str, max_words: int) -> str:
    words = text.split()
    if len(words) <= max_words:
        return text
    return " ".join(words[:max_words])


def estimate_read_time(slides: list) -> float:
    """TikTok read time: 2s base per slide + 0.2s per word in body/text."""
    total = len(slides) * 2.0
    for slide in slides:
        body_text = ((slide.get("body") or "") + " " + (slide.get("text") or "")).strip()
        if body_text:
            total += word_count(body_text) * 0.2
    return round(total, 1)


_VALID_CTAS = {
    "Lien en bio",
    "Continuer",
    "Lire la suite",
    "Découvrir mon message",
    "Découvre le message complet",
}

def enforce_limits(content: dict) -> dict:
    """Enforce word-count limits per slide type."""
    limits = {
        "cover":   {"title": 8},
        "content": {"title": 8, "body": 21},   # -15% vs 25
        "cta":     {"title": 10},
    }
    for slide in content.get("slides", []):
        stype = slide.get("type", "")
        for field, max_w in limits.get(stype, {}).items():
            if slide.get(field):
                slide[field] = truncate_words(slide[field], max_w)
        if stype == "cta":
            cta = (slide.get("cta") or "").replace("🔗", "").strip()
            slide["cta"] = cta if cta in _VALID_CTAS else "Lien en bio"
    return content


def pick_layout(seed_str: str) -> str:
    """Deterministically pick oracle | minimal | mystique from seed string."""
    h = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
    return ["oracle", "minimal", "mystique"][h % 3]


# ---------------------------------------------------------------------------
# Word history — forbidden word tracking across last N posts
# ---------------------------------------------------------------------------

def _load_word_history() -> list:
    try:
        with open(WORD_HISTORY_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def save_word_history(moment: str, slides: list) -> None:
    """Append combined slide text; keep last 20 entries."""
    history = _load_word_history()
    combined = " ".join(
        (s.get("title") or "") + " " + (s.get("body") or "") + " " +
        (s.get("text") or "") + " " + (s.get("action") or "")
        for s in slides
    ).lower()
    history.append({"moment": moment, "text": combined})
    if len(history) > 20:
        history = history[-20:]
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(WORD_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def get_forbidden_words(last_n: int = 10) -> list:
    """Return tracked words that appear in the last n history entries."""
    history = _load_word_history()
    recent = history[-last_n:] if len(history) > last_n else history
    combined = " ".join(e.get("text", "") for e in recent)
    return [w for w in TRACKED_WORDS if w in combined]
