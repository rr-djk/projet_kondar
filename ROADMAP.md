# ROADMAP.md — SENTINELLE CNC

Généré par `planner` le 2026-04-14.
Source : `ARCHITECTURE.md`, `DESIGN.md`, `AGENTS.md`.

**Légende des dépendances** : `[T-X]` signifie "dépend de la tâche X terminée".

---

## Phase 0 — Fondations du projet (Lane B)

Objectif : poser l'environnement, les constantes partagées et le contrat IPC avant toute implémentation métier. Cette phase débloque toutes les autres.

| Tâche | Fichier | Agent | Dépend de |
|---|---|---|---|
| 0.1 | Scaffold arborescence `sentinelle/` | implementation-specialist | — |
| 0.2 | `config.py` — 14 constantes | implementation-specialist | T-0.1 |
| 0.3 | `protocol.py` — `AcousticEvent`, `to_json`, `from_json` | implementation-specialist | T-0.2 |
| 0.4 | `state.py` — FSM 8 états, 2 flags indépendants | implementation-specialist | T-0.3 |

**Jalon 0** : `config.py`, `protocol.py`, `state.py` importables sans erreur. Aucune dépendance hardware.

---

## Phase 1A — Lane A : pilier acoustique Pi (parallèle à Phase 1B)

Objectif : implémenter les composants Pi. Peut progresser en parallèle avec la Lane B.

| Tâche | Fichier | Agent | Dépend de |
|---|---|---|---|
| 1A.1 | `acoustic/analyzer.py` — fonctions pures FFT | implementation-specialist | T-0.2 |
| 1A.2 | `acoustic/baseline.py` — `BaselineStore` (état mutable isolé) | implementation-specialist | T-1A.1 |
| 1A.3 | `acoustic/capture.py` — adapter sounddevice | implementation-specialist | T-1A.1, T-1A.2 |
| 1A.4 | `acoustic/server.py` — asyncio WebSocket port 8765 | implementation-specialist | T-0.3 |
| 1A.5 | `main_pi.py` — orchestration Pi | implementation-specialist | T-1A.1, T-1A.2, T-1A.3, T-1A.4 |

**Jalon 1A** : `python main_pi.py` démarre, serveur écoute sur 8765, events JSON valides émis sur signal synthétique.

---

## Phase 1B — Lane B : composants laptop sans hardware (parallèle à Phase 1A)

Objectif : implémenter les quatre modules purs. Aucun hardware requis, tous testables en isolation.

| Tâche | Fichier | Agent | Dépend de |
|---|---|---|---|
| 1B.1 | `visual/gcode_parser.py` — `parse_gcode() -> List[Segment]` | implementation-specialist | T-0.2 |
| 1B.2 | `visual/obstacle.py` — HSV → `BoundingBox \| None` | implementation-specialist | T-0.2 |
| 1B.3 | `visual/planner.py` — A* 50×50, timeout 150ms | implementation-specialist | T-0.2 |
| 1B.4 | `ipc/ws_client.py` — `AcousticLink`, reconnect backoff | implementation-specialist | T-0.3 |

**Jalon 1B** : 4 modules importables, testables avec données synthétiques, zéro hardware.

---

## Phase 2 — Tests unitaires (parallèle à Phase 1A)

Objectif : valider toutes les fonctions pures avant l'intégration. Peut être écrite au fil des modules Lane B.

| Tâche | Fichier | Agent | Cas couverts | Dépend de |
|---|---|---|---|---|
| 2.1 | `tests/test_analyzer.py` | test-automation-engineer | baseline normale, warn 2.0σ, critical 3.0σ, limite 1.9σ, buffer partiel (5 cas) | T-1A.1 |
| 2.2 | `tests/test_gcode_parser.py` | test-automation-engineer | G0+G1 valides, fichier vide, lignes ignorées (3 cas) | T-1B.1 |
| 2.3 | `tests/test_planner.py` | test-automation-engineer | chemin libre, contournement, aucun chemin → None, timeout 150ms (4 cas) | T-1B.3 |
| 2.4 | `tests/test_obstacle.py` | test-automation-engineer | image orange → BoundingBox, image grise → None (2 cas) | T-1B.2 |
| 2.5 | `tests/test_protocol.py` | test-automation-engineer | round-trip JSON ×2, champ manquant → erreur (3 cas) | T-0.3 |
| 2.6 | `tests/test_state.py` | test-automation-engineer | 7 transitions légales, 3 illégales (10 cas) | T-0.4 |

**Jalon 2** : `pytest sentinelle/tests/` → 27/27 verts, zéro hardware, zéro webcam, zéro Pi.

---

## Phase 3 — Lane C : intégration UI (dépend de Jalon 1A + Jalon 1B)

Objectif : assembler les deux lanes dans l'interface unifiée pygame.

| Tâche | Fichier | Agent | Dépend de |
|---|---|---|---|
| 3.1 | `visual/simulator.py` — squelette boucle pygame 60fps, split-screen | implementation-specialist | T-0.4 |
| 3.2 | Intégrer pilier visuel — webcam, A*, overlays trajectoires | implementation-specialist | T-3.1, T-1B.1, T-1B.2, T-1B.3 |
| 3.3 | Intégrer pilier acoustique — queue FSM, overlays, badges, acquittement | implementation-specialist | T-3.2, T-1B.4 |
| 3.4 | `main_laptop.py` — CLI `python main_laptop.py demo.nc [--camera N]`, logging `.jsonl` | implementation-specialist | T-3.3 |

**Jalon 3** : démo visuelle complète reproductible sans Pi — objet orange → trajectoire recalculée → Confirmer → chemin vert. Durée ≤ 30 secondes.

---

## Phase 4 — Test d'intégration bout en bout Pi ↔ Laptop

Objectif : valider le système complet sur hardware réel.

| Tâche | Description | Agent | Dépend de |
|---|---|---|---|
| 4.1 | Test WebSocket Pi → Laptop — latence ≤ 3s mesurée, event reçu, overlay déclenché | test-automation-engineer | T-1A.5, T-3.4 |
| 4.2 | Séquence démo 30s × 3 consécutives — 0 crash, détection obstacle ≤ 200ms, < 1 fausse alerte / 5min | test-automation-engineer | T-4.1 |

**Jalon 4** : tous les critères de succès de `DESIGN.md` satisfaits.

---

## Phase 5 — Review et documentation

| Tâche | Description | Agent | Dépend de |
|---|---|---|---|
| 5.1 | Audit sécurité — validation messages entrants, exposition réseau, comportement sur déconnexion brutale | security-specialist | T-3.4 |
| 5.2 | Code review — pureté fonctions, isolation état mutable, aucune logique métier dans `main_*.py` | code-reviewer | T-3.4 |
| 5.3 | `README.md` — install Pi + Laptop, commandes, séquence démo, hardware requis, note V1/V2 | documentation-writer | T-4.2 |

**Jalon 5** : projet livrable. `pytest` vert, README complet, dépôt public, vidéo de démo.

---

## Chemin critique

```
Phase 0 (config + protocol + state)
    ├── Lane A (1A.1 → 1A.2 → 1A.3 → 1A.4 → 1A.5)
    │       ↘
    │        Phase 2 (tests — au fil des modules)
    └── Lane B (1B.1, 1B.2, 1B.3, 1B.4 — parallèles entre elles)
                        │
            Lane A + Lane B stables
                        │
                    Phase 3 (3.1 → 3.2 → 3.3 → 3.4)
                        │
                    Phase 4 (4.1 → 4.2)
                        │
                    Phase 5 (5.1, 5.2, 5.3)
```

**Parallélisme maximal** : dès la Phase 0 terminée, Lane A et Lane B s'implémentent simultanément. Les tests de Phase 2 s'écrivent dès que chaque module Lane B est stable — pas besoin d'attendre que tous soient terminés.

---

## Récapitulatif des jalons

| Jalon | Critère | Sans hardware |
|---|---|---|
| Jalon 0 | `config`, `protocol`, `state` importables | Oui |
| Jalon 1A | `main_pi.py` démarre, WebSocket opérationnel | Non (Pi requis) |
| Jalon 1B | 4 modules Lane B importables et testables | Oui |
| Jalon 2 | `pytest` 27/27 verts | Oui |
| Jalon 3 | Démo visuelle complète ≤ 30s | Oui (webcam uniquement) |
| Jalon 4 | Critères DESIGN.md satisfaits, reproductible 3× | Non (Pi + webcam) |
| Jalon 5 | Projet livrable, README, dépôt public | — |
