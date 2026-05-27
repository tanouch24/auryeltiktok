# auryeltiktok

Générateur automatique de carousels TikTok pour la spiritualité — 18 PNG par jour en une commande.

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

Une seule commande génère 18 PNG répartis sur 3 séries (matin / aprem / soir).

## Structure des sorties

```
output/
  2026-05-27/
    matin/      ← Phrase de motivation spirituelle
    aprem/      ← Psaume du jour
    soir/       ← Thème spiritualité
```

Chaque dossier contient `content.json` + 6 slides : `01_cover.png` à `06_cta.png`.

> Si le dossier de la date existe déjà, un dossier horodaté `YYYY-MM-DD_HH-MM` est créé automatiquement.

## Structure du projet

```
generate_all.py        # Point d'entrée
generators/
  motivation.py        # Série matin — phrases motivantes
  psalm.py             # Série après-midi — psaume du jour
  spirituality.py      # Série soir — thèmes spirituels
render/
  renderer.py          # Rendu visuel Pillow (1080×1920)
data/
  used_psalms.json     # Historique psaumes utilisés
  used_topics.json     # Historique thèmes utilisés
assets/fonts/          # Polices Cinzel + Lora (auto-téléchargées)
output/                # Sorties générées
requirements.txt
.env.example
```

## Design system

| Propriété | Valeur |
|-----------|--------|
| Dimensions | 1080×1920 (TikTok 9:16) |
| Fond | Dégradé radial `#2D1260` → `#0A0A14` |
| Couleurs | Violet `#6B21A8`, or `#D4AF37`, blanc, crème |
| Typographie | Cinzel (titres) + Lora (corps) |

## Dépannage

- **Clé API manquante** — définir `ANTHROPIC_API_KEY` dans `.env`. Le système bascule sur les templates locaux si l'API est indisponible.
- **Polices non téléchargées** — vérifier la connexion internet au premier lancement.
- **Pillow non installé** — `pip install Pillow`
- **Psaumes / thèmes épuisés** — l'historique se réinitialise automatiquement.
