# auryeltiktok

Générateur automatique de carousels TikTok pour la spiritualité — 12 PNG par jour en une commande.

---

## Installation

```bash
git clone https://github.com/tanouch24/auryeltiktok
cd auryeltiktok
pip install -r requirements.txt
```

## Configuration

Copier `.env.example` en `.env` et renseigner :

```
ANTHROPIC_API_KEY=your_key_here
```

## Utilisation

```bash
python3 generate_all.py
```

Une seule commande génère 12 PNG répartis sur 3 séries (matin / aprem / soir).

## Structure des sorties

```
output/
  2026-05-27/
    matin/
      content.json
      01_cover.png
      02_content_1.png
      03_content_2.png
      04_cta.png
    aprem/
      content.json
      01_cover.png
      02_content_1.png
      03_content_2.png
      04_cta.png
    soir/
      content.json
      01_cover.png
      02_content_1.png
      03_content_2.png
      04_cta.png
```

Chaque série produit exactement **4 slides**. Si le dossier de la date existe déjà, un dossier horodaté `YYYY-MM-DD_HH-MM` est créé automatiquement.

## Format content.json

```json
{
  "serie": "Phrase de motivation spirituelle",
  "moment": "matin",
  "layout": "oracle",
  "slides": [
    {
      "type": "cover",
      "title": "Ce message n'est pas arrivé par hasard",
      "subtitle": "Motivation spirituelle"
    },
    {
      "type": "content",
      "num": 1,
      "title": "Tu n'es pas oublié·e",
      "body": "Même quand rien ne bouge,\nquelque chose travaille\nen silence pour toi."
    },
    {
      "type": "content",
      "num": 2,
      "title": "La réponse arrive",
      "body": "Observe ce qui revient dans ta vie.\nCe n'est pas un hasard."
    },
    {
      "type": "cta",
      "title": "Quel message t'attend ce matin ?",
      "cta": "🔗 Lien en bio"
    }
  ]
}
```

## Structure du projet

```
generate_all.py        # Point d'entrée
generators/
  motivation.py        # Série matin — phrases motivantes
  psalm.py             # Série après-midi — psaume du jour
  spirituality.py      # Série soir — thèmes spirituels
  utils.py             # Scoring, scoring, word history
render/
  renderer.py          # Rendu visuel Pillow (1080×1920) — 3 layouts
data/
  used_psalms.json     # Historique psaumes utilisés
  used_topics.json     # Historique thèmes utilisés
  hooks.json           # Historique titres cover utilisés
  word_history.json    # Historique mots pour filtre anti-répétition
assets/fonts/          # Polices Cinzel + Lora (auto-téléchargées)
output/                # Sorties générées
requirements.txt
.env.example
```

## Design system

| Propriété | Valeur |
|-----------|--------|
| Dimensions | 1080×1920 (TikTok 9:16) |
| Fond | Dégradé radial — 3 variantes (oracle / minimal / mystique) |
| Couleurs | Violet `#6B21A8`, or `#D4AF37`, blanc, crème |
| Typographie | Cinzel (titres) + Lora (corps) |
| Layouts | Sélection automatique par date + série |

## Dépannage

- **Clé API manquante** — définir `ANTHROPIC_API_KEY` dans `.env`. Le système bascule sur les templates locaux si l'API est indisponible.
- **Polices non téléchargées** — vérifier la connexion internet au premier lancement.
- **Pillow non installé** — `pip install Pillow`
- **Psaumes / thèmes épuisés** — l'historique se réinitialise automatiquement.
