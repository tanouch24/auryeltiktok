"""
generators/midi.py — Série MIDI : Psaume du jour, expliqué de façon moderne.
Objectif : profondeur spirituelle, crédibilité, attachement émotionnel.
Ton : calme, profond, humain. Jamais sermon. Jamais lecture religieuse.
CTA engagement uniquement.
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

STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "used_psalms.json"

# ─── 33 Psaumes curatés ──────────────────────────────────────────────────────

_PSALMS = [
    {
        "num": 23,
        "verse": "Le Seigneur est mon berger.\nJe ne manque de rien.",
        "theme": "abandon confiant",
        "context": "une période où tu te sens perdu ou sans direction",
    },
    {
        "num": 27,
        "verse": "Le Seigneur est ma lumière et mon salut.\nDe qui aurais-je peur ?",
        "theme": "courage face à la peur",
        "context": "une période de peur, de doute ou d'incertitude",
    },
    {
        "num": 34,
        "verse": "Le Seigneur est proche des cœurs brisés.\nIl sauve les esprits abattus.",
        "theme": "consolation dans la douleur",
        "context": "une douleur émotionnelle, une déception ou un deuil",
    },
    {
        "num": 46,
        "verse": "Dieu est notre refuge et notre force.\nUn secours toujours présent dans la détresse.",
        "theme": "refuge et force",
        "context": "une période de stress ou de surcharge",
    },
    {
        "num": 91,
        "verse": "Il habitera sous la protection du Très-Haut.\nIl reposera à l'ombre du Tout-Puissant.",
        "theme": "protection divine",
        "context": "un sentiment d'insécurité ou d'anxiété",
    },
    {
        "num": 103,
        "verse": "Il pardonne toutes tes fautes.\nIl guérit toutes tes blessures.",
        "theme": "pardon et guérison",
        "context": "une culpabilité, une blessure intérieure ou un besoin de paix",
    },
    {
        "num": 121,
        "verse": "Je lève les yeux vers les montagnes.\nD'où me viendra le secours ?",
        "theme": "aide et soutien",
        "context": "une attente de réponse ou un besoin d'aide",
    },
    {
        "num": 139,
        "verse": "Tu me scrutes, Seigneur, et tu me connais.\nTu sais quand je m'assieds, quand je me lève.",
        "theme": "être connu et aimé",
        "context": "un sentiment d'incompréhension ou d'invisibilité",
    },
    {
        "num": 37,
        "verse": "Confie ton chemin au Seigneur.\nFais-lui confiance : il agira.",
        "theme": "lâcher-prise et confiance",
        "context": "une impatience ou une attente difficile",
    },
    {
        "num": 40,
        "verse": "Il m'a tiré du gouffre.\nDe la vase et du marécage.",
        "theme": "délivrance et sortie de crise",
        "context": "une période de sortie de crise ou de reconstruction",
    },
    {
        "num": 42,
        "verse": "Comme une biche cherche l'eau vive,\nainsi mon âme te cherche.",
        "theme": "soif de sens",
        "context": "un vide intérieur ou une quête de sens",
    },
    {
        "num": 51,
        "verse": "Crée en moi un cœur pur, ô Dieu.\nRenouvelle en moi un esprit ferme.",
        "theme": "renouveau et recommencement",
        "context": "un désir de repartir à zéro ou de changer",
    },
    {
        "num": 55,
        "verse": "Ô si tu pouvais me donner des ailes de colombe\npour que je vole et trouve le repos.",
        "theme": "désir de paix et d'évasion",
        "context": "une lassitude ou un besoin de calme",
    },
    {
        "num": 62,
        "verse": "Mon âme, repose en Dieu seul.\nMon salut vient de lui.",
        "theme": "ancrage unique",
        "context": "une période de solitude ou de manque de repères",
    },
    {
        "num": 63,
        "verse": "Je te cherche dès l'aube, mon Dieu.\nMon être a soif de toi.",
        "theme": "quête du matin",
        "context": "un matin difficile ou le début d'une nouvelle période",
    },
    {
        "num": 73,
        "verse": "J'étais stupide, je n'y comprenais rien.\nC'est maintenant que je comprends.",
        "theme": "accepter de ne pas comprendre",
        "context": "une situation qui ne fait pas encore sens",
    },
    {
        "num": 84,
        "verse": "Un seul jour dans ta demeure\nvaut mieux que mille ailleurs.",
        "theme": "présence et priorités",
        "context": "une dispersion ou un manque de focus",
    },
    {
        "num": 86,
        "verse": "Dans le jour de ma détresse, je t'appelle.\nTu me répondras.",
        "theme": "certitude d'être entendu",
        "context": "une attente de réponse ou un cri intérieur",
    },
    {
        "num": 90,
        "verse": "Seigneur, apprends-nous à compter nos jours.\nQue nous venions à la sagesse du cœur.",
        "theme": "sagesse et présence",
        "context": "une prise de conscience du temps ou des priorités",
    },
    {
        "num": 107,
        "verse": "Il les a tirés de la détresse.\nIl a réduit la tempête au silence.",
        "theme": "fin de la tempête",
        "context": "une sortie de période difficile ou un calme retrouvé",
    },
    {
        "num": 112,
        "verse": "Il n'a pas peur des mauvaises nouvelles.\nSon cœur tient ferme, il s'appuie sur Dieu.",
        "theme": "stabilité face aux mauvaises nouvelles",
        "context": "une peur de l'avenir ou d'une mauvaise nouvelle imminente",
    },
    {
        "num": 116,
        "verse": "J'aime le Seigneur : il entend\nle cri de ma supplication.",
        "theme": "être entendu",
        "context": "un sentiment d'isolement ou de non-reconnaissance",
    },
    {
        "num": 118,
        "verse": "La pierre qu'ont rejetée les bâtisseurs\nest devenue la pierre d'angle.",
        "theme": "retournement de situation",
        "context": "un rejet, une sous-estimation ou une valeur cachée",
    },
    {
        "num": 119,
        "verse": "Ta parole est une lampe sur mes pas.\nUne lumière sur ma route.",
        "theme": "direction et lumière",
        "context": "un manque de direction ou une période de flou",
    },
    {
        "num": 126,
        "verse": "Ceux qui sèment dans les larmes\nmoissonnent dans la joie.",
        "theme": "persévérance et récompense",
        "context": "une période d'effort sans résultat visible ou de larmes",
    },
    {
        "num": 131,
        "verse": "Je n'ai pas le cœur ambitieux.\nJe me tiens calme et tranquille.",
        "theme": "humilité et simplicité",
        "context": "une agitation ou une course après des objectifs qui ne sont pas les tiens",
    },
    {
        "num": 138,
        "verse": "Au jour où je t'appelais, tu m'as répondu.\nTu as mis la force en mon âme.",
        "theme": "réponse et force",
        "context": "un besoin de confirmation ou un signe attendu",
    },
    {
        "num": 143,
        "verse": "Fais-moi entendre le matin ton amour.\nCar en toi j'ai mis ma confiance.",
        "theme": "confiance du matin",
        "context": "le début d'une journée incertaine ou difficile",
    },
    {
        "num": 145,
        "verse": "Le Seigneur est proche de tous ceux qui l'invoquent.\nDe tous ceux qui l'invoquent vraiment.",
        "theme": "proximité divine",
        "context": "un sentiment de distance ou d'abandon",
    },
    {
        "num": 147,
        "verse": "Il guérit les cœurs brisés,\nil panse leurs blessures.",
        "theme": "guérison émotionnelle",
        "context": "une blessure récente ou ancienne non cicatrisée",
    },
    {
        "num": 31,
        "verse": "Je t'ai remis mon sort.\nTu m'as racheté, Seigneur, Dieu fidèle.",
        "theme": "confiance totale",
        "context": "une situation hors de contrôle qui demande lâcher-prise",
    },
    {
        "num": 100,
        "verse": "Criez de joie pour Dieu, terre entière.\nServez le Seigneur avec joie.",
        "theme": "joie et gratitude",
        "context": "une invitation à la légèreté et à la reconnaissance",
    },
    {
        "num": 150,
        "verse": "Que tout ce qui respire\nloue le Seigneur.",
        "theme": "célébration et existence",
        "context": "une invitation à être reconnaissant d'être en vie",
    },
]


# ─── CTA midi — engagement uniquement ────────────────────────────────────────

_MIDI_CTAS = [
    ("Ce message te parle ?",           "Commente si tu ressens ça"),
    ("Tu avais besoin d'entendre ça.",  "Écris reçu en commentaire"),
    ("Observe cette journée.",          "Observe les prochains jours"),
    ("Ce psaume est pour toi.",         "Écris oui en commentaire"),
    ("Ça résonne en toi ?",             "Réponds SIGNE en commentaire"),
    ("Tu l'as vu arriver ?",            "Commente si tu t'y reconnais"),
    ("Ce n'est pas un hasard.",         "Écris reçu en commentaire"),
]


def _pick_midi_cta(today: str) -> tuple[str, str]:
    h = int(hashlib.md5(f"midi-cta-{today}".encode()).hexdigest(), 16)
    return _MIDI_CTAS[h % len(_MIDI_CTAS)]


# ─── Fallback ────────────────────────────────────────────────────────────────

FALLBACK = {
    "serie":  "Psaume du jour",
    "moment": "midi",
    "layout": "lune",
    "slides": [
        {
            "type":     "cover",
            "title":    "Psaume 23.",
            "subtitle": "Pour toi aujourd'hui.",
        },
        {
            "type":  "content",
            "num":   1,
            "title": "Pour ceux qui attendent.",
            "body":  "Le Seigneur est mon berger.\nJe ne manque de rien.",
        },
        {
            "type": "revelation",
            "text": "Ce silence ne veut pas dire abandon.",
        },
        {
            "type":  "cta",
            "title": "Ce message te parle ?",
            "cta":   "Commente si tu ressens ça",
        },
    ],
}


# ─── State helpers ───────────────────────────────────────────────────────────

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


def _pick_psalm(used: list, today: str) -> dict:
    available = [p for p in _PSALMS if p["num"] not in used]
    if not available:
        available = list(_PSALMS)
    h = int(hashlib.md5(today.encode()).hexdigest(), 16)
    return available[h % len(available)]


# ─── Prompt builder ──────────────────────────────────────────────────────────

def _build_prompt_psaume(psalm: dict, forbidden_str: str,
                          cta_title: str, cta_text: str) -> str:
    return f"""Génère un carousel TikTok "Psaume du jour" sur le Psaume {psalm['num']} en JSON.

RÔLE : Auryel — compte TikTok spirituel moderne. Tu expliques un psaume de façon émotionnelle et humaine.
Format : 4 slides. Ton doux, profond, humain. Jamais sermon. Jamais lecture religieuse lourde.

VERSET :
"{psalm['verse']}"

THÈME : {psalm['theme']}
S'adresse à quelqu'un qui traverse : {psalm['context']}

RÈGLE D'OR DU TON :
Tu parles à quelqu'un qui souffre en silence, pas à une congrégation.
Chaque phrase doit sonner comme un ami proche qui comprend vraiment.

EXEMPLES DE BON TON :
  ✓ "Ce passage parle des périodes où tout semble bloqué."
  ✓ "Le silence ne veut pas dire abandon."
  ✓ "Ce n'est pas un retard. C'est une protection."
  ✓ "Tu n'es pas seul dans ça."
  ✓ "Il y a des moments où on ne comprend pas encore. C'est normal."
  ✓ "Ce que tu portes depuis des semaines, ce verset en parle."
EXEMPLES DE MAUVAIS TON À ÉVITER ABSOLUMENT :
  ✗ "Ce psaume nous enseigne la sainte vertu de l'obéissance divine."
  ✗ "L'Éternel nous guide sur le chemin de la lumière céleste."
  ✗ "Ce passage révèle la profondeur de notre relation avec le divin."
  ✗ "Dieu veut que tu comprennes cette vérité fondamentale."

STRUCTURE OBLIGATOIRE — exactement 4 slides :

SLIDE 1 — cover :
  type = "cover"
  title = "Psaume {psalm['num']}."  — VERBATIM, ne modifie pas
  subtitle MAX 5 MOTS — pour qui ce psaume parle spécifiquement aujourd'hui
  Basé sur le contexte : "{psalm['context']}"
  EXEMPLES subtitle :
    "Pour ceux qui attendent." / "Pour les cœurs fatigués." /
    "Pour toi, ce soir." / "Pour les cœurs brisés." /
    "Pour ceux qui doutent." / "Pour ceux qui souffrent en silence."
  RÈGLE : parle à une personne précise qui vit quelque chose de précis

SLIDE 2 — content :
  type = "content", num = 1
  title MAX 5 MOTS — à qui ce psaume parle concrètement aujourd'hui
  EXEMPLES title :
    "Pour ceux qui attendent." / "Pour les cœurs fatigués." / "Pour toi, ce soir."
  body MAX 15 MOTS — le verset, 2 lignes séparées par \\n
  Utilise le verset VERBATIM ou très légèrement simplifié

SLIDE 3 — revelation :
  type = "revelation"
  text MAX 8 MOTS — l'explication moderne en 1 phrase directe
  Ce n'est PAS une paraphrase du verset. C'est ce que ça dit concrètement à quelqu'un qui souffre.
  EXEMPLES :
    "Même dans la nuit, tu n'es pas seul."
    "Ce silence ne veut pas dire abandon."
    "Ce retard n'est pas un refus."
    "Quelque chose te tient. Même quand tu doutes."
    "Tu n'as pas besoin de tout comprendre maintenant."
    "Cette attente a un sens. Même si tu ne le vois pas."
    "Ce que tu traverses ne te définit pas."
    "Tenir, c'est déjà une victoire."

SLIDE 4 — cta :
  type = "cta"
  title = "{cta_title}"
  cta = "{cta_text}"

INTERDIT absolu : {forbidden_str}, sermon, vocabulaire religieux lourd, jugement, culpabilité,
  "péché", style pasteur, citation spirituelle générique, lien en bio, WhatsApp
Tout en français.

JSON uniquement :
{{
  "serie": "Psaume du jour",
  "moment": "midi",
  "slides": [
    {{"type": "cover",      "title": "Psaume {psalm['num']}.", "subtitle": "Pour ceux qui..."}},
    {{"type": "content",    "num": 1, "title": "...", "body": "...\\n..."}},
    {{"type": "revelation", "text": "..."}},
    {{"type": "cta",        "title": "{cta_title}", "cta": "{cta_text}"}}
  ]
}}"""


# ─── Main generator ──────────────────────────────────────────────────────────

def generate(api_key: str, date_override: str = "") -> dict:
    """Returns a content.json-compatible dict with exactly 4 slides."""
    today         = date_override or date.today().isoformat()
    forbidden     = get_forbidden_words()
    forbidden_str = ", ".join(forbidden) if forbidden else "aucun"
    seed_offset   = pick_seed_offset(f"midi-{today}")
    layout        = pick_layout(f"midi-{today}", category="midi")

    used   = _load_used()
    psalm  = _pick_psalm(used, today)
    cta_title, cta_text = _pick_midi_cta(today)

    prompt = _build_prompt_psaume(psalm, forbidden_str, cta_title, cta_text)

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
                logger.warning(f"[midi] attempt {attempt+1} parse error: {exc}")
                continue

            slides = content.get("slides", [])
            if len(slides) != 4:
                logger.warning(f"[midi] attempt {attempt+1}: {len(slides)} slides")
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
                logger.warning(f"[midi] attempt {attempt+1} validation: {errors}")
                best = content
                continue

            best = content
            break

        if best is None:
            logger.warning("[midi] all attempts failed, using fallback")
            return _apply_fallback(layout, seed_offset, cta_title, cta_text)

        used.append(psalm["num"])
        _save_used(used)
        save_word_history("midi", best["slides"])
        logger.info(f"[midi] Generated — Psaume {psalm['num']} layout: {layout}")
        return best

    except Exception as e:
        logger.warning(f"[midi] Using fallback (error: {e})")
        return _apply_fallback(layout, seed_offset, cta_title, cta_text)


def _apply_fallback(layout: str, seed_offset: int = 0,
                    cta_title: str = "Ce message te parle ?",
                    cta_text: str = "Commente si tu ressens ça") -> dict:
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
    save_word_history("midi", fb["slides"])
    return fb
