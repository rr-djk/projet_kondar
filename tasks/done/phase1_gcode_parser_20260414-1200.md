---
status: todo
type: feature
priority: high
assigned_to: implementation-specialist
started_at: null
depends_on: [T-0.2]
files_touched: [sentinelle/visual/gcode_parser.py]
related_to: null
---

# T-1B.1 — gcode_parser.py

## Description
Implémenter `parse_gcode(path: str) -> list[Segment]` qui parse un fichier G-code
(.nc) et extrait uniquement les commandes G0/G1.

## Spécifications
- `Point` dataclass : `x: float`, `y: float` (coordonnées en mm)
- `Segment` dataclass : `start: Point`, `end: Point`, `move_type: str` ("rapid" | "feed")
- G0 = mouvement rapide ("rapid"), G1 = mouvement d'usinage ("feed")
- Position initiale = (0, 0)
- Lignes non-G0/G1 ignorées (commentaires, M-codes, S-codes, etc.)
- Fichier vide → liste vide
- Fonction pure : pas d'état global, pas d'effet de bord
- Constantes depuis `config.py` (WORKSPACE_MM)

## Critères d'acceptation
- Importable sans erreur
- Parse correctement un fichier G-code avec G0 et G1 mélangés
- Retourne liste vide pour fichier vide ou sans G0/G1
- Coordonnées en mm, conversion pixels déléguée au simulateur
