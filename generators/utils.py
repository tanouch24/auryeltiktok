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
    "Écris reçu en commentaire",
    "Commente si tu ressens ça",
    "Quel chiffre as-tu choisi ?",
    "Observe les prochains jours",
    "Tu le ressens ?",
    "Réponds SIGNE en commentaire",
    "Écris OUI si c'est toi",
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

    # Pad to allow boundary matching for contractions like "j'", "m'"
    hook_padded = " " + hook_lower + " "
    personal_patterns = [
        "tu ", " toi", " ton ", " ta ", " tes ", "vous", "votre", "vos",
        "je ", "j'", " il ", " elle ", "mon ", " ma ", " mes ",
        "m'", "me ", " on ",
    ]
    if any(p in hook_padded for p in personal_patterns):
        score += 15

    urgency = ["aujourd'hui", "ce soir", "ce matin", "maintenant",
               "bientôt", "avant de", "insiste", "insistent"]
    if any(w in hook_lower for w in urgency):
        score += 10

    mystery = ["secret", "caché", "cache", "révèle", "message", "signe",
               "hasard", "veut", "attend", "arrive", "ceci", "pourquoi",
               "refus", "douleur", "revient", "reviennent", "encore",
               "vrai", "ignore", "caches", "oublie", "resiste", "refuse"]
    if any(w in hook_lower for w in mystery):
        score += 10

    # Bonus for interrogative-form hooks (strong curiosity signal)
    if hook_lower.startswith("pourquoi") or hook_lower.endswith("?"):
        score += 10

    abstract = ["âme", "coeur", "cœur", "guérison", "révélation", "énergie",
                "vibration", "destin", "univers", "guides", "lumière"]
    for w in abstract:
        if w in hook_lower:
            score -= 8

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


def truncate_body_smart(text: str, max_words: int) -> str:
    """Truncate at max_words, preferring last complete sentence boundary."""
    words = text.split()
    if len(words) <= max_words:
        return text
    truncated = " ".join(words[:max_words])
    # Walk backwards through sentence-ending punctuation
    for m in reversed(list(re.finditer(r'[.!?]', truncated))):
        before = truncated[:m.end()].strip()
        if len(before.split()) >= max(3, max_words // 3):
            return before
    return truncated


def estimate_read_time(slides: list) -> float:
    """TikTok read time: 2s base per slide + 0.2s per word in body/text."""
    total = len(slides) * 2.0
    for slide in slides:
        body_text = ((slide.get("body") or "") + " " + (slide.get("text") or "")).strip()
        if body_text:
            total += word_count(body_text) * 0.2
    return round(total, 1)


_VALID_CTAS = {
    # ── Matin : engagement uniquement ──────────────────────────────────────
    "Écris reçu en commentaire",
    "Quel chiffre as-tu choisi ?",
    "Observe les prochains jours",
    "Tu le ressens ?",
    "Commente si tu ressens ça",
    "Commente ton mot",
    "Observe cette journée",
    "Écris oui en commentaire",
    "Réponds avec ton ressenti",
    # ── Soir engagement ────────────────────────────────────────────────────
    "Tu l'as vécu aussi ?",
    "Commente si tu t'y reconnais",
    # ── Midi : engagement ──────────────────────────────────────────────────
    "Ce message te parle ?",
    "Tu avais besoin d'entendre ça.",
    "Ça parle de toi ?",
    # ── Soir conversion douce ──────────────────────────────────────────────
    "Lien dans la bio",
    "Lien en bio",
    "Tirage gratuit → bio",
    "Guidance gratuite → bio",
    "Découvre ton message → bio",
    "Voir mon tirage",
    "Découvre le message complet",
    # ── Legacy ──────────────────────────────────────────────────────────────
    "Lire le message",
    "Ouvrir le psaume",
    "Lire le psaume",
    "Écris ton chiffre en bas",
}

CONTENT_BLACKLIST = [
    "révélation", "énergie", "vibration", "destin", "âme",
    "lumière intérieure", "entités", "malédiction", "blocages occultes",
    "chemin s'illumine", "vérité attend",
    "dieu voit", "dieu sait tout", "pensées secrètes", "culpabilité",
    "jugement", "tu caches", "vérité cachée", "prophétie",
]

# Slide types that carry a "text" field instead of title/body
_REVELATION_TYPES = {"revelation"}


def validate_content(content: dict) -> list:
    """Returns list of validation error strings. Empty = passes all quality gates."""
    errors = []
    slides = content.get("slides", [])

    if content.get("hook_score", 0) < 50:
        errors.append(f"hook_score={content.get('hook_score',0)} < 78")

    for i, slide in enumerate(slides):
        stype  = slide.get("type", "")
        title  = (slide.get("title") or "")
        body   = (slide.get("body") or "")
        all_t  = (title + " " + body).lower()

        for word in CONTENT_BLACKLIST:
            if word.lower() in all_t:
                errors.append(f"slide {i+1} blacklist: '{word}'")

        if stype == "content":
            t_words = len(title.split()) if title else 0
            b_words = len(body.replace("\n", " ").split()) if body else 0
            b_lines = [l for l in body.split("\n") if l.strip()]
            if t_words > 5:
                errors.append(f"slide {i+1} title {t_words} words > 5")
            if b_words > 15:
                errors.append(f"slide {i+1} body {b_words} words > 15")
            if len(b_lines) > 2:
                errors.append(f"slide {i+1} body {len(b_lines)} lines > 2")

    return errors


def enforce_limits(content: dict) -> dict:
    """Enforce word-count limits and apply French text corrections per slide."""
    limits = {
        "cover":      {"title": 6},
        "content":    {"title": 5, "body": 15},
        "message":    {"title": 5, "body": 15},
        "revelation": {"text": 10},
        "cta":        {"title": 10},
    }
    for slide in content.get("slides", []):
        stype = slide.get("type", "")
        for field, max_w in limits.get(stype, {}).items():
            if slide.get(field):
                raw = slide[field]
                trimmed = truncate_body_smart(raw, max_w) if field == "body" else truncate_words(raw, max_w)
                slide[field] = fix_french_text(trimmed)
        if stype == "cta":
            # Strip common spirituality emoji before validation
            raw_cta = (slide.get("cta") or "")
            for ch in ("🔗", "🔮", "✨", "⭐", "🌙", "💫", "🌟"):
                raw_cta = raw_cta.replace(ch, "")
            cta = raw_cta.strip()
            slide["cta"] = cta if cta in _VALID_CTAS else "Lien en bio"
    return content


_ALL_LAYOUTS = [
    "oracle", "minimal", "mystique",
    "lune", "tarot", "cosmique", "silhouette",
]

# Layout pools par moment/registre — pondérés vers les meilleurs visuels
_CATEGORY_LAYOUTS = {
    # ── MATIN : lumineux, minimal, moderne — guidance/motivation ──
    "matin":  ["minimal", "oracle", "lune", "minimal", "tarot", "oracle", "lune"],
    # ── MIDI : calme, profond, spirituel — psaume ──
    "midi":   ["lune", "mystique", "tarot", "lune", "mystique", "cosmique", "tarot"],
    "amour":  ["oracle", "tarot", "silhouette", "oracle", "tarot", "oracle", "silhouette"],
    # ── SOIR destin/mystique : profond, cinématographique, élégant ──
    "soir":   ["mystique", "lune", "cosmique", "lune", "mystique", "silhouette", "cosmique"],
    "destin": ["mystique", "lune", "cosmique", "lune", "mystique", "silhouette", "cosmique"],
    # ── SOIR astro : cosmique, spatial, assertif ──
    "soir_astro": ["cosmique", "mystique", "lune", "cosmique", "lune", "mystique", "tarot"],
    "astro":      ["cosmique", "mystique", "lune", "cosmique", "lune", "mystique", "tarot"],
    # ── Legacy / autres ──
    "choix": ["tarot", "oracle", "tarot", "mystique", "tarot", "cosmique", "oracle"],
}


def pick_layout(seed_str: str, category: str = "default") -> str:
    """Deterministically pick a layout from seed string. Pass category for themed selection."""
    h    = int(hashlib.md5(seed_str.encode()).hexdigest(), 16)
    pool = _CATEGORY_LAYOUTS.get(category, _ALL_LAYOUTS)
    return pool[h % len(pool)]


def pick_seed_offset(seed_str: str) -> int:
    """Return a daily seed offset 0-99 for visual variation (different star placement, text Y)."""
    h = int(hashlib.md5(f"voffset-{seed_str}".encode()).hexdigest(), 16)
    return h % 100


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
    if len(history) > 30:
        history = history[-30:]
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    with open(WORD_HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(history, f, ensure_ascii=False, indent=2)


def fix_french_text(text: str) -> str:
    """Remove dangling words from word-count truncation; loop until stable."""
    if not text:
        return text
    PATTERNS = [
        # Conjunctions
        r'[\s,]+(et|ou|mais|car|donc|ni|or)[,.\s]*$',
        # Relative pronouns and prepositions
        r'\s+(qui|que|dont|ou|vers|pour|avec|sans|sur|dans|par|en|y)[,.\s]*$',
        # Bare prepositions that always need a complement
        r'\s+(a|de)[,.\s]*$',
        # Definite/indefinite articles, partitives, demonstratives
        r'\s+(le|la|les|l|un|une|des|du|au|ce|cet|cette|ces)\s*$',
        # Possessive adjectives (always need a noun after)
        r'\s+(tes|mes|ses|nos|vos|leurs)\s*$',
        # Negation/auxiliary fragments
        r'\s+n.(?:est|a|y|en)\s*$',
        r'\s+(ne|pas|plus|jamais|rien)\s*$',
        # Multi-word: "que/comme/si/quand + pronoun"
        r'\s+(?:que|comme|si|quand)\s+(?:tu|vous|je|il|elle|ils|elles|on)\s*$',
        # Dangling relative clause: "qui/que + conjugated verb"
        r'\s+(?:qui|que)\s+(?:est|sont|était|sera|a|ont|avait|peut|veut|doit)\s*$',
        # Stranded infinitive after modal
        r'\s+\w+\s+(?:être|avoir|faire|savoir|vouloir|pouvoir|devoir|aller)\s*$',
        # Lone conjugated être/avoir needing a predicate
        r'\s+(?:est|sont|était|seront|sera)\s*$',
        # Reflexive verbs needing a complement ("se met", "se trouve", "se fait"...)
        r'\s+se\s+(?:met|mets|mettent|trouvent?|fait|font|passe(?:nt)?|tient|tiennent)\s*$',
        # Trailing punctuation artifacts
        r'[,;]+\s*$',
    ]
    for _ in range(5):   # iterate until stable (max 5 passes)
        prev = text
        for pat in PATTERNS:
            candidate = re.sub(pat, '', text, flags=re.IGNORECASE).strip()
            if len(candidate.split()) >= 3:  # never strip below 3 words
                text = candidate
        text = re.sub(r'  +', ' ', text).strip()
        if text == prev:
            break
    return text


def get_forbidden_words(last_n: int = 10) -> list:
    """Return tracked words that appear in the last n history entries."""
    history = _load_word_history()
    recent = history[-last_n:] if len(history) > last_n else history
    combined = " ".join(e.get("text", "") for e in recent)
    return [w for w in TRACKED_WORDS if w in combined]
