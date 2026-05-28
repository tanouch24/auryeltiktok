"""
generators/motivation.py — Série MATIN : Guidance / Motivation / Spirituel moderne.
3 formats rotatifs : Mot du jour · Citation spirituelle · Mini guidance.
Style : lumineux, élégant, profond — jamais fake guru, jamais kitsch.
CTA engagement uniquement — jamais lien bio.
Anti-répétition : 100 mots, mémoire 30 jours.
"""
import hashlib
import json
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

HOOKS_FILE       = Path(__file__).resolve().parent.parent / "data" / "hooks.json"
MOTS_STATE_FILE  = Path(__file__).resolve().parent.parent / "data" / "used_mots.json"

# ─── Format rotation ─────────────────────────────────────────────────────────

_FORMATS = ["mot_du_jour", "citation", "guidance"]


def _pick_format(today: str) -> str:
    h = int(hashlib.md5(f"matin-format-{today}".encode()).hexdigest(), 16)
    return _FORMATS[h % len(_FORMATS)]


# ─── Mot du jour pool — 100 mots uniques ────────────────────────────────────

_MOTS_DU_JOUR = [
    # Rapport à soi
    "patience", "confiance", "lâcher-prise", "courage", "clarté",
    "douceur", "présence", "repos", "authenticité", "force",
    "silence", "équilibre", "ancrage", "persévérance", "bienveillance",
    "gratitude", "paix", "espoir", "renouveau", "frontières",
    # États internes
    "légèreté", "acceptation", "recul", "lucidité", "sérénité",
    "fierté", "compassion", "discernement", "sensibilité", "ouverture",
    "fluidité", "tendresse", "dignité", "vitalité", "intégrité",
    "curiosité", "résilience", "volonté", "calme", "détermination",
    # Action / mouvement
    "avancer", "choisir", "poser", "observer", "écouter",
    "lâcher", "recommencer", "ralentir", "décider", "oser",
    "refuser", "accueillir", "traverser", "agir", "attendre",
    "respirer", "nommer", "bouger", "créer", "persister",
    # Relations / extérieur
    "limites", "respect", "vérité", "honnêteté", "écoute",
    "lien", "séparation", "retour", "rupture", "réconciliation",
    "distance", "besoin", "désir", "liberté", "choix",
    "pardon", "mémoire", "attachement", "solitude", "rencontre",
    # Temps / rythme
    "maintenant", "aujourd'hui", "timing", "processus", "transition",
    "cycle", "changement", "continuité", "recommencement", "pause",
    # Sagesse / profondeur
    "intuition", "sens", "conscience", "intention", "chemin",
    "réponse", "question", "profondeur", "réveil", "direction",
]


def _load_used_mots() -> list:
    try:
        with open(MOTS_STATE_FILE, "r", encoding="utf-8") as f:
            data = json.load(f)
            return data if isinstance(data, list) else []
    except (FileNotFoundError, json.JSONDecodeError):
        return []


def _save_used_mot(mot: str) -> None:
    used = _load_used_mots()
    if mot in used:
        used.remove(mot)
    used.append(mot)
    if len(used) > 30:
        used = used[-30:]
    MOTS_STATE_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(MOTS_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump(used, f, ensure_ascii=False, indent=2)


def _pick_mot(today: str) -> str:
    used = set(_load_used_mots())
    available = [m for m in _MOTS_DU_JOUR if m not in used]
    if not available:
        available = list(_MOTS_DU_JOUR)
    h = int(hashlib.md5(f"matin-mot-{today}".encode()).hexdigest(), 16)
    return available[h % len(available)]


# ─── Citation pool ───────────────────────────────────────────────────────────

_CITATIONS = [
    # Attente & timing
    "Tout ne répond pas tout de suite.",
    "Ce n'est pas un refus. C'est un timing.",
    "Pas maintenant ne veut pas dire jamais.",
    "Arrêter d'attendre, c'est aussi une décision.",
    "Certains moments demandent juste d'attendre.",
    # Silence & intuition
    "Ce silence aussi te protège.",
    "Ton silence peut être une réponse.",
    "Ton intuition n'invente rien.",
    "Ce que tu ressens est une information.",
    "Tu savais déjà. Tu avais besoin qu'on te le confirme.",
    # Lâcher & forcer
    "Lâche. Ce n'est pas abandonner.",
    "Forcer, c'est souvent bloquer.",
    "Ce que tu fuis te rattrape. Ce que tu traverses te libère.",
    "Parfois la meilleure décision c'est de ne pas en prendre.",
    # Relations & personnes
    "Ce qui repart revient. Ou était censé partir.",
    "Certaines personnes ne sont pas censées rester.",
    "Tu mérites une réponse. Pas une excuse.",
    "Le problème n'est pas lui. C'est le doute.",
    "Certains partent pour mieux revenir. Certains partent, c'est tout.",
    # Authenticité & limites
    "Tu n'as pas à tout expliquer.",
    "Tu peux être fort et avoir besoin d'aide.",
    "Tu n'as pas à faire semblant que ça va.",
    "Ce qui te coûte quelque chose te dit quelque chose.",
    "Tu mérites ce que tu donnes aux autres.",
    # Changement & conscience
    "Tu n'attires pas ce que tu veux. Tu attires ce que tu es.",
    "Ce que tu ignores en toi dirige ta vie.",
    "Ce vide que tu ressens a une forme.",
    "Quelque chose change. Tu ne sais pas encore quoi.",
    "Ce n'est pas trop tard. C'est juste compliqué.",
    # Présence & moment
    "Ce que tu ressens là n'est pas une coïncidence.",
    "Ce matin compte. Même si tu n'en vois pas encore pourquoi.",
]


def _pick_citation(today: str) -> str:
    h = int(hashlib.md5(f"matin-citation-{today}".encode()).hexdigest(), 16)
    return _CITATIONS[h % len(_CITATIONS)]


# ─── CTA matin — jamais de lien bio ─────────────────────────────────────────

_MATIN_CTAS = [
    ("Tu le ressens ?",          "Écris reçu en commentaire"),
    ("Quel mot te parle ?",      "Commente ton mot"),
    ("Ça résonne ?",             "Écris oui en commentaire"),
    ("Observe cette journée.",   "Observe cette journée"),
    ("Ce mot t'a trouvé.",       "Commente si tu t'y reconnais"),
    ("Tu as vu ça venir ?",      "Écris oui en commentaire"),
]


def _pick_matin_cta(today: str) -> tuple[str, str]:
    h = int(hashlib.md5(f"matin-cta-{today}".encode()).hexdigest(), 16)
    return _MATIN_CTAS[h % len(_MATIN_CTAS)]


# ─── Fallback ────────────────────────────────────────────────────────────────

FALLBACK = {
    "serie":  "Guidance Matin",
    "moment": "matin",
    "layout": "minimal",
    "slides": [
        {
            "type":     "cover",
            "title":    "Mot du jour : confiance.",
            "subtitle": "Guidance Auryel",
        },
        {
            "type":  "content",
            "num":   1,
            "title": "Ce mot t'est destiné",
            "body":  "Tu traverses quelque chose.\nElle est déjà en toi.",
        },
        {
            "type": "revelation",
            "text": "Commence avec confiance.",
        },
        {
            "type":  "cta",
            "title": "Tu le ressens ?",
            "cta":   "Écris reçu en commentaire",
        },
    ],
}


# ─── Prompt builders ─────────────────────────────────────────────────────────

def _build_prompt_mot(mot: str, forbidden_str: str,
                      cta_title: str, cta_text: str) -> str:
    return f"""Génère un carousel TikTok matin "Mot du jour" sur le mot "{mot}" en JSON.

CONTEXTE : compte TikTok spirituel 500K abonnés. Matin. Ton humain, direct, court.

RÈGLE D'OR DU TON — lis attentivement :
Chaque ligne doit sonner comme si tu l'envoyais par SMS à une amie.
- 1 idée par ligne, maximum 5 mots par ligne
- phrases directes, sans poésie ni explication
- jamais de phrases longues avec "qui", "que", "parce que"
- si ça ressemble à un livre de développement personnel → recommence

EXEMPLES DE BON TON (pour que tu comprennes le niveau) :
✓ "Ce mot n'est pas un hasard."
✓ "Quelque chose résiste. C'est normal."
✓ "Laisse le temps travailler."
✓ "Tu n'as pas à tout régler aujourd'hui."

EXEMPLES DE MAUVAIS TON À ÉVITER ABSOLUMENT :
✗ "Cette situation te prépare à quelque chose de plus grand."
✗ "L'univers t'envoie un signe important aujourd'hui."
✗ "Tu traverses une période de transformation profonde."

4 SLIDES OBLIGATOIRES :

SLIDE 1 — cover :
  type = "cover"
  title = "Mot du jour : {mot}."  — VERBATIM, ne change pas
  subtitle = "Guidance Auryel"

SLIDE 2 — content :
  type = "content", num = 1
  title MAX 5 MOTS — observation directe sur "{mot}" aujourd'hui
  BONS exemples title :
    "Tout ne se répond pas vite." (pour patience)
    "Tu lâches ou tu tiens ?" (pour lâcher-prise)
    "Ce calme a du sens." (pour paix)
  body MAX 10 MOTS — exactement 2 lignes courtes séparées par \\n
  Chaque ligne = 1 phrase courte de 4-5 mots max
  BONS exemples body :
    "Ce qui résiste te prépare.\\nLaisse le temps travailler."
    "Tu n'as pas besoin de forcer.\\nCe sera là quand il le faut."
    "Ce n'est pas un retard.\\nC'est une protection."
  MAUVAIS exemples à ne pas reproduire :
    "Cette situation t'invite à pratiquer {mot} et à faire confiance."  ← trop long
    "Ce mot te demande de regarder en toi avec bienveillance."  ← trop flou

SLIDE 3 — revelation :
  type = "revelation"
  text MAX 6 MOTS — 1 phrase ultra courte, directe
  BONS exemples :
    "Attends. Ça arrive."
    "Pas maintenant. Pas encore."
    "Lâche. Ça reviendra."
    "Observe ce qui s'ouvre."
    "Garde ce mot avec toi."

SLIDE 4 — cta :
  type = "cta"
  title = "{cta_title}"
  cta = "{cta_text}"

INTERDIT absolu : {forbidden_str}, énergie, alignement, univers, cosmos, manifestation, vibration, âme, entités, lien en bio
Tout en français.

JSON uniquement :
{{
  "serie": "Guidance Matin",
  "moment": "matin",
  "slides": [
    {{"type": "cover",      "title": "Mot du jour : {mot}.", "subtitle": "Guidance Auryel"}},
    {{"type": "content",    "num": 1, "title": "...", "body": "...\\n..."}},
    {{"type": "revelation", "text": "..."}},
    {{"type": "cta",        "title": "{cta_title}", "cta": "{cta_text}"}}
  ]
}}"""


def _build_prompt_citation(citation: str, forbidden_str: str,
                            cta_title: str, cta_text: str) -> str:
    return f"""Génère un carousel TikTok matin autour de la citation : "{citation}" en JSON.

CONTEXTE : compte TikTok spirituel 500K abonnés. Matin. Ton humain, direct, court.

RÈGLE D'OR DU TON :
Chaque ligne = 1 idée, maximum 5 mots. Comme un message à une amie.
Pas de phrases longues. Pas d'explications. Juste l'essentiel.

EXEMPLES DE BON TON :
✓ "Tu forçais peut-être quelque chose."
✓ "Certaines choses arrivent quand tu lâches."
✓ "Pas quand tu pousses."
✓ "Tu le savais déjà."

EXEMPLES DE MAUVAIS TON :
✗ "Cette citation résonne profondément avec ce que tu traverses en ce moment."
✗ "L'univers t'invite à réfléchir à cette vérité fondamentale."

4 SLIDES OBLIGATOIRES :

SLIDE 1 — cover :
  type = "cover"
  title = "{citation}"  — VERBATIM, ne modifie pas
  subtitle = "Guidance Auryel"

SLIDE 2 — content :
  type = "content", num = 1
  title MAX 5 MOTS — ce à quoi cette citation s'applique concrètement maintenant
  BONS exemples title :
    "Tu forçais peut-être." / "Tu attendais une permission." / "Ça parle de quelqu'un."
  body MAX 10 MOTS — 2 lignes courtes séparées par \\n, 4-5 mots chacune
  Parle d'une situation réelle que quelqu'un peut vivre (relation, attente, silence, doute)
  BONS exemples body :
    "Tu forces quelque chose en ce moment.\\nLâche. Ça viendra autrement."
    "Il y a un silence dans ta vie.\\nCette phrase en parle."
    "Tu attendais peut-être une permission.\\nLa voilà."
  Concret. Tutoiement. Pas de généralités.

SLIDE 3 — revelation :
  type = "revelation"
  text MAX 6 MOTS — 1 seule phrase directe, comment agir ou observer aujourd'hui
  BONS exemples :
    "Lâche. Observe ce qui arrive."
    "Arrête de forcer. Attends."
    "Ce silence a une réponse."
    "Tu sais déjà ce que c'est."

SLIDE 4 — cta :
  type = "cta"
  title = "{cta_title}"
  cta = "{cta_text}"

INTERDIT absolu : {forbidden_str}, énergie, alignement, univers, cosmos, vibration, âme, entités, développement personnel générique, lien en bio
Tout en français.

JSON uniquement :
{{
  "serie": "Guidance Matin",
  "moment": "matin",
  "slides": [
    {{"type": "cover",      "title": "{citation}", "subtitle": "Guidance Auryel"}},
    {{"type": "content",    "num": 1, "title": "...", "body": "...\\n..."}},
    {{"type": "revelation", "text": "..."}},
    {{"type": "cta",        "title": "{cta_title}", "cta": "{cta_text}"}}
  ]
}}"""


def _build_prompt_guidance(forbidden_str: str,
                            cta_title: str, cta_text: str) -> str:
    return f"""Génère un carousel TikTok matin "Guidance du jour" en JSON.

CONTEXTE : compte TikTok spirituel 500K abonnés. Matin. Ton humain, direct, court.

RÈGLE D'OR DU TON :
Parle comme si tu envoyais un message vocal à une amie ce matin.
Phrases courtes. 1 idée par ligne. Maximum 5 mots par ligne.
Pas de grandes déclarations. Pas de poésie. Juste du vrai.

SI UNE PHRASE RESSEMBLE À :
  — un livre de développement personnel
  — un compte Pinterest spirituel
  — une notification d'appli méditation
→ recommence. Ce n'est pas le bon ton.

EXEMPLES DE BON TON :
✓ "Ce matin, écoute ce que tu ressens."
✓ "Pas une coïncidence. Une direction."
✓ "Quelque chose essaie de te parler."
✓ "Observe. Ne force pas."
✓ "Si tu penses à quelqu'un ce matin, c'est un signe."
✓ "Ce que tu retardes depuis des semaines..."
✓ "Tu n'as pas dormi. Ton intuition travaillait."

EXEMPLES DE MAUVAIS TON :
✗ "L'univers t'envoie des signes pour te guider vers ta destinée."
✗ "Ton énergie du matin définit la vibration de ta journée."
✗ "Cette journée est une opportunité de transformation profonde."

4 SLIDES OBLIGATOIRES :

SLIDE 1 — cover :
  type = "cover"
  title MAX 7 MOTS — observation du matin, immédiatement reconnaissable
  subtitle = "Guidance Auryel"
  BONS hooks — patterns TikTok qui fonctionnent (crée quelque chose de similaire) :
    "Si tu penses à quelqu'un ce matin..."
    "Tu n'as pas dormi. Ton intuition travaillait."
    "Ce que tu retardes depuis des semaines."
    "Tu attends une réponse. Elle approche."
    "Ce matin est différent. Observe."
    "Ton intuition a quelque chose à dire."
    "Ce silence autour de toi a un sens."
    "Quelque chose essaie de te parler."
    "Observe ce qui bloque en toi."
  RÈGLE : tutoiement, situation concrète, jamais abstrait
  BONUS : les meilleurs hooks commencent par une situation que le lecteur vit vraiment

SLIDE 2 — content :
  type = "content", num = 1
  title MAX 5 MOTS — l'observation concrète, sobre
  body MAX 10 MOTS — 2 lignes séparées par \\n, 4-5 mots chacune
  Parle d'une situation réelle (attente, silence, doute, changement, intuition)
  BONS exemples body :
    "Pas une coïncidence.\\nUne direction."
    "Tu portes quelque chose depuis trop longtemps.\\nLâche ce matin."
    "Ce que tu ressens là est vrai.\\nSuis ça."
  Concret. Direct. Pas d'explication ni d'abstraction.

SLIDE 3 — revelation :
  type = "revelation"
  text MAX 6 MOTS — le message central, ultra court
  BONS exemples :
    "Suis ça aujourd'hui."
    "Observe. La réponse est là."
    "Ce que tu ressens est juste."
    "Laisse venir ce qui vient."
    "Pas de force. Juste de la présence."

SLIDE 4 — cta :
  type = "cta"
  title = "{cta_title}"
  cta = "{cta_text}"

INTERDIT absolu : {forbidden_str}, énergie, alignement, univers, cosmos, vibration, âme, entités, fake guru, pontifiant, lien en bio
Tout en français.

JSON uniquement :
{{
  "serie": "Guidance Matin",
  "moment": "matin",
  "slides": [
    {{"type": "cover",      "title": "...", "subtitle": "Guidance Auryel"}},
    {{"type": "content",    "num": 1, "title": "...", "body": "...\\n..."}},
    {{"type": "revelation", "text": "..."}},
    {{"type": "cta",        "title": "{cta_title}", "cta": "{cta_text}"}}
  ]
}}"""


# ─── Hooks file helpers ──────────────────────────────────────────────────────

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


# ─── Main generator ──────────────────────────────────────────────────────────

def generate(api_key: str, date_override: str = "") -> dict:
    """Returns a content.json-compatible dict with exactly 4 slides."""
    today       = date_override or date.today().isoformat()
    layout      = pick_layout(f"matin-{today}", category="matin")
    seed_offset = pick_seed_offset(f"matin-{today}")
    forbidden   = get_forbidden_words()
    forbidden_str = ", ".join(forbidden) if forbidden else "aucun"

    fmt                 = _pick_format(today)
    cta_title, cta_text = _pick_matin_cta(today)
    mot = None

    if fmt == "mot_du_jour":
        mot    = _pick_mot(today)
        prompt = _build_prompt_mot(mot, forbidden_str, cta_title, cta_text)
    elif fmt == "citation":
        citation = _pick_citation(today)
        prompt   = _build_prompt_citation(citation, forbidden_str, cta_title, cta_text)
    else:
        prompt = _build_prompt_guidance(forbidden_str, cta_title, cta_text)

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
                logger.warning(f"[motivation] attempt {attempt+1} parse error: {exc}")
                continue

            slides = content.get("slides", [])
            if len(slides) != 4:
                logger.warning(f"[motivation] attempt {attempt+1}: {len(slides)} slides")
                continue

            content = enforce_limits(content)
            slides  = content["slides"]

            if slides[3].get("type") == "cta":
                slides[3]["cta"]   = cta_text
                slides[3]["title"] = cta_title

            content["layout"]            = layout
            content["_seed_offset"]      = seed_offset
            content["hook_score"]        = score_hook(slides[0].get("title", ""))
            content["read_time_seconds"] = estimate_read_time(slides)
            content["emotion_score"]     = emotion_score(slides)
            content["curiosity_score"]   = curiosity_score(slides)

            errors = validate_content(content)
            if errors:
                logger.warning(f"[motivation] attempt {attempt+1} validation: {errors}")
                best = content
                continue

            best = content
            break

        if best is None:
            logger.warning("[motivation] all attempts failed, using fallback")
            return _apply_fallback(layout, seed_offset, cta_title, cta_text)

        if mot:
            _save_used_mot(mot)
        _save_hook(best["slides"][0].get("title", ""))
        save_word_history("matin", best["slides"])
        logger.info(f"[motivation] Generated — format: {fmt} layout: {layout}")
        return best

    except Exception as e:
        logger.warning(f"[motivation] Using fallback (error: {e})")
        return _apply_fallback(layout, seed_offset, cta_title, cta_text)


def _apply_fallback(layout: str, seed_offset: int = 0,
                    cta_title: str = "Tu le ressens ?",
                    cta_text: str = "Écris reçu en commentaire") -> dict:
    fb = dict(FALLBACK)
    fb["slides"] = [dict(s) for s in FALLBACK["slides"]]
    fb["slides"][3]["title"] = cta_title
    fb["slides"][3]["cta"]   = cta_text
    fb["layout"]             = layout
    fb["_seed_offset"]       = seed_offset
    fb["hook_score"]         = score_hook(fb["slides"][0]["title"])
    fb["read_time_seconds"]  = estimate_read_time(fb["slides"])
    fb["emotion_score"]      = emotion_score(fb["slides"])
    fb["curiosity_score"]    = curiosity_score(fb["slides"])
    save_word_history("matin", fb["slides"])
    return fb
