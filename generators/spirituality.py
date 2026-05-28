"""
generators/spirituality.py — Série SOIR : Storytelling émotionnel TikTok.
Mini histoires réelles → projection émotionnelle → envie naturelle de consulter.
Structure : Problème → Émotion → Tirage/Guidance → Révélation + CTA doux.
~50% CTA conversion (soft), ~50% engagement.
"""
import hashlib
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

STATE_FILE = Path(__file__).resolve().parent.parent / "data" / "used_topics.json"
HOOKS_FILE = Path(__file__).resolve().parent.parent / "data" / "hooks.json"

# ─── 16 thèmes émotionnels ───────────────────────────────────────────────────

_THEMES = [
    {
        "id":       "retour",
        "label":    "retour amoureux",
        "hooks":    [
            "Il est revenu 3 mois plus tard.",
            "Elle a rappelé sans prévenir.",
            "J'avais arrêté d'attendre.",
            "Il a écrit après des mois.",
        ],
        "emotion":  "Je n'y croyais plus. Mais quelque chose me disait que ce n'était pas fini.",
        "turning":  [
            "J'ai fait un tirage gratuit.",
            "J'ai posé la question au tirage.",
            "J'ai fait le tirage ce soir-là.",
        ],
        "reveal":   [
            "3 jours après, il a écrit.",
            "Ce que j'ai lu m'a coupé le souffle.",
            "Elle avait tout vu d'avance.",
        ],
    },
    {
        "id":       "silence",
        "label":    "silence et attente",
        "hooks":    [
            "Il ne répondait plus.",
            "3 semaines sans nouvelles.",
            "Ce silence durait trop longtemps.",
            "Elle avait tout arrêté d'un coup.",
        ],
        "emotion":  "J'avais failli tout effacer. Mais mon intuition criait de ne pas bouger.",
        "turning":  [
            "J'ai fait un tirage gratuit.",
            "J'ai fait le tirage ce soir-là.",
            "J'ai posé la question au tirage.",
        ],
        "reveal":   [
            "Le lendemain, son message est arrivé.",
            "Ce que j'ai vu m'a glacée.",
            "Ce silence cachait quelque chose.",
        ],
    },
    {
        "id":       "tromperie",
        "label":    "intuition et tromperie",
        "hooks":    [
            "Je pensais qu'il me trompait.",
            "Mon intuition criait. Je l'ignorais.",
            "Quelque chose ne collait pas.",
            "Je sentais quelque chose. Sans preuves.",
        ],
        "emotion":  "Je n'avais aucune preuve. Mais ce sentiment ne partait pas.",
        "turning":  [
            "J'ai fait un tirage gratuit.",
            "J'ai posé la question au tirage.",
            "J'ai fait le tirage ce soir-là.",
        ],
        "reveal":   [
            "Ce que j'ai lu m'a choquée.",
            "Et elle avait raison.",
            "La vérité était là depuis le début.",
        ],
    },
    {
        "id":       "ex",
        "label":    "ex qui revient",
        "hooks":    [
            "Mon ex a refait surface.",
            "Il a rouvert la conversation.",
            "Elle a liké mes photos après 6 mois.",
            "Mon ex pensait encore à moi.",
        ],
        "emotion":  "Je ne savais pas quoi en penser. Une partie de moi voulait répondre.",
        "turning":  [
            "J'ai fait un tirage avant de répondre.",
            "J'ai posé la question au tirage.",
            "J'ai fait le tirage ce soir-là.",
        ],
        "reveal":   [
            "Ce que j'ai lu a tout changé.",
            "La réponse m'a surprise.",
            "Ce retour avait un sens.",
        ],
    },
    {
        "id":       "message",
        "label":    "message qui n'arrive pas",
        "hooks":    [
            "J'attendais un message depuis des jours.",
            "Il avait lu. Pas répondu.",
            "Ce double tick bleu qui tue.",
            "Elle avait vu. Rien.",
        ],
        "emotion":  "Je vérifiais mon téléphone toutes les heures. C'était épuisant.",
        "turning":  [
            "J'ai fait un tirage gratuit.",
            "J'ai posé la question au tirage.",
            "J'ai fait le tirage ce soir-là.",
        ],
        "reveal":   [
            "Le message est arrivé 2 jours après.",
            "Ce que j'ai lu m'a coupé le souffle.",
            "Il y avait une raison à ce silence.",
        ],
    },
    {
        "id":       "regrets",
        "label":    "regrets et ce qu'il/elle ressent",
        "hooks":    [
            "Il regrette. Je le sens.",
            "Elle pense encore à moi.",
            "Je sais qu'il n'a pas tourné la page.",
            "Ce silence, c'est de la honte.",
        ],
        "emotion":  "J'avais besoin de savoir. Pas pour revenir. Juste pour comprendre.",
        "turning":  [
            "J'ai fait un tirage gratuit.",
            "J'ai posé la question ce soir-là.",
            "J'ai demandé ce qu'il ressentait.",
        ],
        "reveal":   [
            "Ce que j'ai lu m'a surprise.",
            "Il regrettait. Vraiment.",
            "La réponse m'a figée.",
        ],
    },
    {
        "id":       "jalousie",
        "label":    "jalousie et sentiment caché",
        "hooks":    [
            "Il regardait mes stories. Sans parler.",
            "Elle aimait tout ce que je postais.",
            "Ce regard ne mentait pas.",
            "Il faisait semblant de ne pas regarder.",
        ],
        "emotion":  "Je ne voulais pas m'emballer. Mais c'était évident pour moi.",
        "turning":  [
            "J'ai fait un tirage gratuit.",
            "J'ai posé la question au tirage.",
            "J'ai fait le tirage pour en avoir le cœur net.",
        ],
        "reveal":   [
            "Ce que je ressentais était réel.",
            "La réponse ne laissait aucun doute.",
            "Ce que j'ai lu m'a tout confirmé.",
        ],
    },
    {
        "id":       "intuition",
        "label":    "intuition forte",
        "hooks":    [
            "Mon intuition me criait quelque chose.",
            "Je savais que quelque chose allait changer.",
            "Ce pressentiment ne me lâchait pas.",
            "Je ne savais pas l'expliquer.",
        ],
        "emotion":  "Les autres me disaient que j'imaginais. Mais je savais.",
        "turning":  [
            "J'ai fait un tirage pour en être sûre.",
            "J'ai posé la question au tirage.",
            "J'ai fait le tirage ce soir-là.",
        ],
        "reveal":   [
            "Mon intuition avait raison depuis le début.",
            "Ce que j'ai lu m'a donné la chair de poule.",
            "Je n'étais pas folle.",
        ],
    },
    {
        "id":       "obsession",
        "label":    "pensées obsessionnelles",
        "hooks":    [
            "Je n'arrêtais pas de penser à lui.",
            "Elle occupait toutes mes pensées.",
            "Je voulais arrêter. Je n'y arrivais pas.",
            "Son prénom revenait sans arrêt.",
        ],
        "emotion":  "Je savais que c'était trop. Mais je ne pouvais pas m'arrêter.",
        "turning":  [
            "J'ai fait un tirage gratuit.",
            "J'ai posé la question au tirage.",
            "J'ai fait le tirage pour comprendre.",
        ],
        "reveal":   [
            "La réponse m'a libérée de quelque chose.",
            "Ce que j'ai lu m'a tout expliqué.",
            "Ce n'était pas de l'obsession.",
        ],
    },
    {
        "id":       "relation_cachee",
        "label":    "relation cachée ou ambiguë",
        "hooks":    [
            "On ne s'appelait pas couple. Mais on l'était.",
            "Il ne voulait pas de titre.",
            "Entre nous, c'était flou. Intentionnellement.",
            "Ses actes disaient autre chose.",
        ],
        "emotion":  "Je ne savais plus où j'en étais. Je méritais une réponse.",
        "turning":  [
            "J'ai fait un tirage gratuit.",
            "J'ai posé la question au tirage.",
            "J'ai fait le tirage ce soir-là.",
        ],
        "reveal":   [
            "Ce que j'ai lu a tout clarifié.",
            "La réponse m'a surprise.",
            "Je savais enfin où j'en étais.",
        ],
    },
    {
        "id":       "sentiments",
        "label":    "sentiments non dits",
        "hooks":    [
            "Il n'a jamais dit qu'il m'aimait.",
            "Elle cachait ce qu'elle ressentait.",
            "Ces mots qu'il ne disait jamais.",
            "Elle m'aimait. Elle ne le savait pas.",
        ],
        "emotion":  "J'avais besoin de savoir. Ces non-dits me pesaient trop.",
        "turning":  [
            "J'ai fait un tirage gratuit.",
            "J'ai posé la question au tirage.",
            "J'ai demandé ce qu'il ressentait vraiment.",
        ],
        "reveal":   [
            "Ce que j'ai lu m'a figée.",
            "Il ressentait tout. Il ne savait pas le dire.",
            "La réponse m'a donné la chair de poule.",
        ],
    },
    {
        "id":       "separation",
        "label":    "séparation et deuil amoureux",
        "hooks":    [
            "On s'est séparés il y a 2 semaines.",
            "Elle est partie du jour au lendemain.",
            "Après 3 ans, c'était fini.",
            "Je ne m'y attendais pas du tout.",
        ],
        "emotion":  "Je ne comprenais pas. Rien ne l'avait laissé voir venir.",
        "turning":  [
            "J'ai fait un tirage gratuit.",
            "J'ai posé la question au tirage.",
            "J'ai fait le tirage ce soir-là.",
        ],
        "reveal":   [
            "Cette séparation avait un sens.",
            "Ce que j'ai lu m'a aidée à avancer.",
            "La réponse m'a choquée.",
        ],
    },
    {
        "id":       "blocage",
        "label":    "blocage émotionnel",
        "hooks":    [
            "Je n'arrivais plus à avancer.",
            "Toujours le même schéma.",
            "Je tournais en rond depuis des mois.",
            "Quelque chose m'empêchait de lâcher.",
        ],
        "emotion":  "Je savais que je devais lâcher. Mais je ne savais pas comment.",
        "turning":  [
            "J'ai fait un tirage gratuit.",
            "J'ai posé la question au tirage.",
            "J'ai fait le tirage pour comprendre.",
        ],
        "reveal":   [
            "La réponse était là depuis longtemps.",
            "Ce que j'ai lu m'a libérée.",
            "Ce qui bloquait n'était pas ce que je croyais.",
        ],
    },
    {
        "id":       "synchronicite",
        "label":    "synchronicité et connexion",
        "hooks":    [
            "On a pensé l'un à l'autre en même temps.",
            "Il m'a écrit 1 minute après que j'aie pensé à lui.",
            "Ces coïncidences. Trop de fois.",
            "Chaque fois que je pensais à elle, elle apparaissait.",
        ],
        "emotion":  "Je ne croyais pas aux coïncidences. Jusqu'à là.",
        "turning":  [
            "J'ai fait un tirage gratuit.",
            "J'ai posé la question au tirage.",
            "J'ai fait le tirage pour comprendre ce lien.",
        ],
        "reveal":   [
            "Ce lien était réel et actif.",
            "Ce que j'ai lu m'a glacée.",
            "Ce n'était pas un hasard.",
        ],
    },
    {
        "id":       "guidance",
        "label":    "guidance et tournant de vie",
        "hooks":    [
            "Je ne savais plus quelle décision prendre.",
            "J'étais à un carrefour.",
            "Une décision importante m'attendait.",
            "Je sentais qu'un changement approchait.",
        ],
        "emotion":  "J'avais peur de faire le mauvais choix. Comme toujours.",
        "turning":  [
            "J'ai fait un tirage avant de décider.",
            "J'ai posé la question au tirage.",
            "J'ai fait le tirage ce soir-là.",
        ],
        "reveal":   [
            "Ce que j'ai lu m'a donné la direction.",
            "La réponse était claire.",
            "Je savais enfin quoi faire.",
        ],
    },
    {
        "id":       "destin",
        "label":    "destin amoureux",
        "hooks":    [
            "Je me demandais si c'était lui.",
            "Ce lien résiste à tout.",
            "On s'est perdus 3 fois. Et retrouvés.",
            "Destinés ou pas ?",
        ],
        "emotion":  "Je voulais savoir si ce lien avait un sens ou si je m'inventais des histoires.",
        "turning":  [
            "J'ai fait un tirage gratuit.",
            "J'ai posé la question au tirage.",
            "J'ai fait le tirage ce soir-là.",
        ],
        "reveal":   [
            "Ce que j'ai lu m'a donné la chair de poule.",
            "Ce lien n'était pas dans ma tête.",
            "La réponse a tout changé pour moi.",
        ],
    },
]


def _pick_theme(used: list) -> dict:
    available = [t for t in _THEMES if t["id"] not in used]
    if not available:
        available = list(_THEMES)
    return random.choice(available)


# ─── CTA soir ────────────────────────────────────────────────────────────────

_CTA_ENGAGEMENT = [
    ("Tu l'as vécu aussi ?",        "Commente si tu t'y reconnais"),
    ("Tu te reconnais ?",           "Commente si tu ressens ça"),
    ("Toi aussi tu attends ?",      "Écris oui en commentaire"),
    ("Tu vis ça en ce moment ?",    "Commente si tu ressens ça"),
]

_CTA_CONVERSION = [
    ("Tu veux savoir ce qu'il ressent ?", "Tirage gratuit → bio"),
    ("Tu veux une réponse claire ?",      "Guidance gratuite → bio"),
    ("Et toi, tu veux savoir ?",          "Découvre ton message → bio"),
    ("Tu attends un retour ?",            "Tirage gratuit → bio"),
]


def _pick_soir_cta(today: str) -> tuple[str, str]:
    h = int(hashlib.md5(f"soir-cta-{today}".encode()).hexdigest(), 16)
    if h % 2 == 0:
        return _CTA_CONVERSION[(h // 2) % len(_CTA_CONVERSION)]
    return _CTA_ENGAGEMENT[(h // 2) % len(_CTA_ENGAGEMENT)]


# ─── Fallback ────────────────────────────────────────────────────────────────

FALLBACK = {
    "serie":  "Histoire du soir",
    "moment": "soir",
    "layout": "mystique",
    "slides": [
        {
            "type":     "cover",
            "title":    "Il ne répondait plus.",
            "subtitle": "Histoire vraie",
        },
        {
            "type":  "content",
            "num":   1,
            "title": "3 semaines de silence",
            "body":  "J'avais failli tout effacer.\nMais quelque chose me disait d'attendre.",
        },
        {
            "type": "revelation",
            "text": "J'ai fait un tirage gratuit.",
        },
        {
            "type": "whatsapp",
            "messages": [
                {"from": "user",   "text": "Il va revenir ?"},
                {"from": "auryel", "text": "Oui.\nMais son ego résiste encore."},
            ],
        },
        {
            "type":  "cta",
            "title": "Le lendemain, son message est arrivé.",
            "cta":   "Tu l'as vécu aussi ?",
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


# ─── Prompt builder ──────────────────────────────────────────────────────────

def _build_prompt_story(theme: dict, forbidden_str: str,
                         cta_title: str, cta_text: str) -> str:
    hooks_str   = "\n".join(f'    "{h}"' for h in theme["hooks"])
    turning_str = "\n".join(f'    "{t}"' for t in theme["turning"])
    reveal_str  = "\n".join(f'    "{r}"' for r in theme["reveal"])

    return f"""Génère un carousel TikTok "mini histoire vraie" sur le thème "{theme["label"]}" en JSON.

RÔLE : Auryel — compte TikTok de guidance. Tu racontes UNE MINI HISTOIRE RÉELLE, émotionnelle.
Format : storytelling TikTok, 4 slides. Court. Percutant. Naturel. Jamais une pub. Jamais abstrait.

RÈGLE D'OR DU TON :
EXEMPLES DE BON TON :
  ✓ "Il ne répondait plus."
  ✓ "Mais je sentais qu'il mentait."
  ✓ "J'ai fait un tirage gratuit."
  ✓ "Ce que j'ai vu m'a glacée."
  ✓ "Le lendemain, son message est arrivé."
EXEMPLES DE MAUVAIS TON À ÉVITER ABSOLUMENT :
  ✗ "L'univers t'envoie un signe important."
  ✗ "Cette situation révèle quelque chose de profond en toi."
  ✗ "Les énergies autour de cette personne sont intenses."
  ✗ "Une guidance peut t'aider à avancer sur ton chemin."
  ✗ "Votre connexion transcende le niveau physique."

STRUCTURE OBLIGATOIRE — exactement 4 slides :

SLIDE 1 — cover (LE PROBLÈME / HOOK) :
  type = "cover"
  title MAXIMUM 7 MOTS — la situation, ultra courte, comme si tu commençais une conversation
  subtitle = "Histoire vraie"
  EXEMPLES pour "{theme["label"]}" :
{hooks_str}
  RÈGLES :
  - phrase courte et directe, jamais abstraite
  - première personne ou situation concrète
  - le lecteur se reconnaît en 0.5 seconde

SLIDE 2 — content (L'ÉMOTION / LA TENSION) :
  type = "content", num = 1
  title MAXIMUM 5 MOTS — l'état ou la situation, sobre
  EXEMPLES title : "3 semaines de silence" / "J'essayais d'avancer" / "Je ne comprenais pas"
  body MAXIMUM 15 MOTS — 2 lignes séparées par \\n, MAX 8 MOTS PAR LIGNE
  ligne 1 = ce qui se passait (concret)
  ligne 2 = l'émotion ou résistance interne
  EXEMPLES body :
    "J'avais failli tout effacer.\\nMais quelque chose me retenait."
    "Je voulais arrêter d'y penser.\\nJe n'y arrivais pas."
    "J'avais besoin de savoir.\\nJe ne supportais plus l'incertitude."
  RÈGLES : court, concret, humain — jamais poétique ni abstrait

SLIDE 3 — revelation (LE TOURNANT — LE TIRAGE) :
  type = "revelation"
  text MAXIMUM 8 MOTS — le moment où tu passes à l'action
  FORMULE RECOMMANDÉE : "J'ai fait un tirage gratuit."
  EXEMPLES pour ce thème :
{turning_str}
  EXEMPLES universels :
    "J'ai fait un tirage gratuit."
    "J'ai fait le tirage ce soir-là."
    "J'ai posé la question au tirage."
  RÈGLE ABSOLUE : naturel, action concrète, jamais publicitaire

SLIDE 4 — whatsapp (LA DISCUSSION WHATSAPP — IMMERSION) :
  type = "whatsapp"
  messages = tableau JSON de 2 à 4 messages
  STRUCTURE : 1-2 questions "user" + 1-2 réponses "auryel"
  RÈGLES POUR LES QUESTIONS (user) :
    - Naturelles, courtes (max 8 mots)
    - En lien direct avec le thème "{theme["label"]}"
    EXEMPLES : "Il va revenir ?" / "Il pense encore à moi ?" / "C'était un signe ?"
  RÈGLES POUR AURYEL — TENSION ET FRUSTRATION :
    - Max 10 mots au total (1-2 lignes séparées par \\n si besoin)
    - RÉPONSE PARTIELLE OBLIGATOIRE : Auryel ne révèle JAMAIS tout. La dernière
      réponse laisse toujours quelque chose d'incomplet ou d'ambigu — le lecteur
      doit vouloir en savoir plus.
    - Spécifique, mystérieux, jamais générique. Crée de la frustration positive.
    BONS exemples ✓ :
      "Il relit encore votre dernière conversation."
      "Tu ne sais pas encore tout."
      "Quelqu'un influence encore cette relation."
      "Ce n'est pas terminé.\\nMais rien n'est gagné."
      "Oui.\\nMais pas comme tu l'imagines."
      "Il cache encore quelque chose."
      "Elle attend. Son ego résiste encore."
      "Il y a une chose que tu ignores."
    MAUVAIS exemples ✗ :
      "Il pense encore à toi."  ← trop générique, révèle trop
      "L'univers vous relie."  ← interdit
      "Il t'aime profondément."  ← trop complet, tue le suspense
      "Oui, il reviendra."  ← trop direct, pas de tension

  HÉSITATION OPTIONNELLE — à utiliser au maximum 1 fois :
    Auryel peut d'abord envoyer "..." seul avant sa vraie réponse.
    Utilise uniquement quand la question de l'utilisateur est émotionnellement forte.
    Cela crée un micro-délai qui rend la conversation plus réelle.
    Exemple :
      {{"from": "auryel", "text": "..."}},
      {{"from": "auryel", "text": "Il relit encore vos messages."}}

  3 STRUCTURES POSSIBLES — choisis selon l'émotion du thème :
    Court (2 messages) : 1 question user → 1 réponse auryel incomplète
    Moyen (3 messages) : 1 question user → auryel "..." → auryel révèle partiellement
    Long (4 messages)  : user demande → auryel partiel → user relance → auryel cliffhanger final

SLIDE 5 — cta :
  type = "cta"
  title MAXIMUM 8 MOTS — prolonge l'émotion de la discussion WhatsApp
  EXEMPLES pour ce thème :
{reveal_str}
  EXEMPLES universels :
    "Ce que j'ai vu m'a glacée."
    "La réponse m'a choquée."
    "Et elle avait tout vu."
    "3 jours après, tout s'est confirmé."
  RÈGLE ABSOLUE : JAMAIS une question dans le title — cliffhanger ou révélation courte
  cta = "{cta_text}" — OBLIGATOIRE, ne change pas

INTERDIT ABSOLU : {forbidden_str}, énergie, univers, cosmos, vibration, alignement,
  manifestation, destinée, âme, entités, prophétie, "Réserve", "Achète", "Consultation",
  phrases poétiques floues, citations pseudo-philosophiques

JSON uniquement :
{{
  "serie": "Histoire du soir",
  "moment": "soir",
  "slides": [
    {{"type": "cover",      "title": "...", "subtitle": "Histoire vraie"}},
    {{"type": "content",    "num": 1, "title": "...", "body": "...\\n..."}},
    {{"type": "revelation", "text": "..."}},
    {{"type": "whatsapp",   "messages": [
      {{"from": "user",   "text": "..."}},
      {{"from": "auryel", "text": "..."}}
    ]}},
    {{"type": "cta",        "title": "...", "cta": "{cta_text}"}}
  ]
}}"""


# ─── Main generator ──────────────────────────────────────────────────────────

def generate(api_key: str, date_override: str = "") -> dict:
    """Returns a content.json-compatible dict with exactly 4 slides."""
    today         = date_override or date.today().isoformat()
    forbidden     = get_forbidden_words()
    forbidden_str = ", ".join(forbidden) if forbidden else "aucun"
    seed_offset   = pick_seed_offset(f"soir-{today}")
    layout        = pick_layout(f"soir-{today}", category="soir")

    used  = _load_used()
    theme = _pick_theme(used)
    cta_title, cta_text = _pick_soir_cta(today)

    prompt = _build_prompt_story(theme, forbidden_str, cta_title, cta_text)

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
                logger.warning(f"[spirituality] attempt {attempt+1} parse error: {exc}")
                continue

            slides = content.get("slides", [])
            if len(slides) != 5:
                logger.warning(f"[spirituality] attempt {attempt+1}: {len(slides)} slides (need 5)")
                continue

            content = enforce_limits(content)
            slides  = content["slides"]

            if slides[4].get("type") == "cta":
                slides[4]["cta"] = cta_text
                # Keep Claude's title for the story resolution — do NOT override

            content["layout"]            = layout
            content["_seed_offset"]      = seed_offset
            content["hook_score"]        = score_hook(slides[0].get("title", ""))
            content["read_time_seconds"] = estimate_read_time(slides)
            content["emotion_score"]     = emotion_score(slides)
            content["curiosity_score"]   = curiosity_score(slides)

            errors = validate_content(content)
            if errors:
                logger.warning(f"[spirituality] attempt {attempt+1} validation: {errors}")
                best = content
                continue

            best = content
            break

        if best is None:
            logger.warning("[spirituality] all attempts failed, using fallback")
            return _apply_fallback(layout, seed_offset, cta_title, cta_text)

        used.append(theme["id"])
        _save_used(used)
        _save_hook(best["slides"][0].get("title", ""))
        save_word_history("soir", best["slides"])
        logger.info(f"[spirituality] Generated — theme: {theme['label']} layout: {layout}")
        return best

    except Exception as e:
        logger.warning(f"[spirituality] Using fallback (error: {e})")
        return _apply_fallback(layout, seed_offset, cta_title, cta_text)


def _apply_fallback(layout: str, seed_offset: int = 0,
                    cta_title: str = "Tu l'as vécu aussi ?",
                    cta_text: str = "Commente si tu t'y reconnais") -> dict:
    fb = dict(FALLBACK)
    fb["slides"] = [dict(s) for s in FALLBACK["slides"]]
    fb["slides"][3]["cta"] = cta_text
    fb["layout"]            = layout
    fb["_seed_offset"]      = seed_offset
    fb["hook_score"]        = score_hook(fb["slides"][0]["title"])
    fb["read_time_seconds"] = estimate_read_time(fb["slides"])
    fb["emotion_score"]     = emotion_score(fb["slides"])
    fb["curiosity_score"]   = curiosity_score(fb["slides"])
    save_word_history("soir", fb["slides"])
    return fb
