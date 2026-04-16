# ROADMAP.md — SENTINELLE CNC

Généré par `planner` le 2026-04-14.
Mis à jour le 2026-04-16 par implementation-specialist (Phase 3 complète).
Source : `ARCHITECTURE.md`, `DESIGN.md`, `AGENTS.md`.

**Légende des dépendances** : `[T-X]` signifie "dépend de la tâche X terminée".
**Légende des statuts** : ✅ Terminé | 🔄 En cours | ⏳ En attente

---

## Phase 0 — Fondations du projet

**Jalon 0 ✅** : `config.py`, `protocol.py`, `state.py` importables sans erreur. Aucune dépendance hardware.

---

## Phase 1A — Lane A : pilier acoustique Pi

**Jalon 1A ✅** : `python main_pi.py` démarre, serveur écoute sur 8765, events JSON valides émis sur signal synthétique.

| Tâche | Fichier | Statut | Commit |
|-------|---------|--------|--------|
| 1A.1 | `acoustic/analyzer.py` — fonctions pures FFT | ✅ | — |
| 1A.2 | `acoustic/baseline.py` — `BaselineStore` | ✅ | — |
| 1A.3 | `acoustic/capture.py` — adapter sounddevice | ✅ | — |
| 1A.4 | `acoustic/server.py` — asyncio WebSocket port 8765 | ✅ | — |
| 1A.5 | `main_pi.py` — orchestration Pi | ✅ | `d6eba41` |

---

## Phase 1B — Lane B : composants laptop sans hardware

**Jalon 1B ✅** : 6 modules importables, testables avec données synthétiques, zéro hardware.

| Tâche | Fichier | Statut | Commit |
|-------|---------|--------|--------|
| 1B.1 | `visual/gcode_parser.py` — parse G0/G1 | ✅ | — |
| 1B.2 | `visual/obstacle.py` — HSV → BoundingBox | ✅ | — |
| 1B.2b | `visual/obstacle.py` — ArUco fallback | ✅ | — |
| 1B.3 | `visual/planner.py` — A* 50×50, timeout 150ms | ✅ | — |
| 1B.4 | `ipc/ws_client.py` — AcousticLink daemon | ✅ | — |
| 1B.5 | `ipc/mock_server.py` — émetteur synthétique | ✅ | — |

---

## Phase 2 — Tests unitaires

**Jalon 2 ✅** : `pytest sentinelle/tests/` → 51/51 verts, zéro hardware. CI configuré.

| Tâche | Fichier | Cas | Statut |
|-------|---------|-----|--------|
| 2.1 | `tests/test_analyzer.py` | 5 cas | ✅ |
| 2.2 | `tests/test_gcode_parser.py` | 3 cas | ✅ |
| 2.3 | `tests/test_planner.py` | 4 cas | ✅ |
| 2.4 | `tests/test_obstacle.py` | 2 cas | ✅ |
| 2.4b | `tests/test_obstacle_aruco.py` | 4 cas | ✅ |
| 2.5 | `tests/test_protocol.py` | 3 cas | ✅ |
| 2.6 | `tests/test_state.py` | 10 cas | ✅ |
| 2.7 | `tests/test_ws_client.py` | 4 cas | ✅ |
| 2.8 | `tests/test_mock_server.py` | 2 cas | ✅ |
| 2.9 | `.github/workflows/test.yml` — GitHub CI | — | ✅ |

**Total : 51 tests ✅**

---

## Phase 3 — Lane C : intégration UI

**Jalon 3 ✅** : Démo visuelle complète fonctionnelle sur laptop.

### Tâches terminées

| Tâche | Description | Statut | Commit |
|-------|-------------|--------|--------|
| S0 | TODOs critiques : FSM transitions manquantes, ArUco fallback, config MIN_CONTOUR_AREA | ✅ | `1202004` |
| T-3.1 | Squelette `visual/simulator.py` — pygame 60fps, split-screen 1280×720 (60/40) | ✅ | `3098617` |
| T-3.2 | Intégration pilier visuel — G-code, webcam, A*, overlays | ✅ | `0b7906b` |
| T-3.3 | Intégration pilier acoustique — overlays, badges ONLINE/OFFLINE | ✅ | `e5a5b52` |
| T-3.3-bis | Bouton BASELINE — capture 10s, barre progression, badge "Baseline active" | ✅ | `92f7fcd` |
| T-3.3-ter | Bouton MUTE 30s — compteur faux positifs, badge orange | ✅ | `b819e69` |
| T-3.4 | `main_laptop.py` — CLI + logging JSONL dans `sentinelle/logs/` | ✅ | `2b259ac` |
| — | Mise à jour ROADMAP — Jalon 3 atteint | ✅ | `6c367dc` |
| Bug | Correction palpitations webcam — `_last_camera_frame` cache | ✅ | `b8255d3` |
| Fix | Logs JSONL dans `sentinelle/logs/` au lieu de racine | ✅ | `8dbfb16` |

### Fonctionnalités livrées (Phase 3)

**Interface pygame 1280×720, split 60/40 :**
- ✅ Panel visuel gauche (768px) : G-code, grille légère, preview webcam 160×120
- ✅ Panel données droit (512px) : badges, boutons, état FSM

**Palette Dashboard Industriel :**
- ✅ Fond : `#121212` (Deep Charcoal)
- ✅ Surface : `#1E1E2E` (Dark Slate)
- ✅ Primaire : `#00E5FF` (Cyan Électrique) — trajectoire alternative
- ✅ Alerte : `#FF5252` (Rouge Flash) — trajectoire originale
- ✅ Texte : `#E0E0E0` (Blanc Cassé)
- ✅ Magenta : `#FF00FF` — CHEMIN IMPOSSIBLE

**Pilier Visuel :**
- ✅ Chargement G-code depuis `demo.nc`
- ✅ Trajectoire rouge (originale) / cyan (alternative)
- ✅ Détection obstacle HSV + ArUco fallback
- ✅ Recalcul A* throttlé (5Hz max)
- ✅ Overlay "CHEMIN IMPOSSIBLE" magenta

**Pilier Acoustique :**
- ✅ Badge ONLINE/OFFLINE (5s timeout)
- ✅ Overlays : WARN (jaune), CRITICAL (rouge 50%), EMERGENCY_STOP
- ✅ Acquittement ESPACE après 3s
- ✅ États FSM : AUTO_OPTIMIZE (feed rate -20%), EMERGENCY_STOP (touche R reset)

**Contrôles UI :**
- ✅ Bouton BASELINE : capture 10s, barre progression, badge "Baseline active"
- ✅ Bouton MUTE 30s : compteur faux positifs, badge orange, events ignorés
- ✅ Double-clic protégé (idempotent)

**CLI et Logging :**
- ✅ `python3 -m sentinelle.main_laptop demo.nc [--camera N]`
- ✅ Logging JSONL dans `sentinelle/logs/session_<timestamp>.jsonl`
- ✅ Events : fsm_transition, baseline, obstacle, mute

---

## Phase 4 — Test d'intégration hardware

**Dépend de :** Phase 3 + Raspberry Pi + webcam physique

| Tâche | Description | Statut |
|-------|-------------|--------|
| 4.1 | Test WebSocket Pi → Laptop — latence ≤ 3s, overlay déclenché | ⏳ |
| 4.2 | Séquence démo 30s × 3 — 0 crash, détection ≤ 200ms | ⏳ |
| 4.3 | Vidéo de démo — publication YouTube/LinkedIn | ⏳ |

**Jalon 4** : Critères `DESIGN.md` satisfaits + vidéo publiée.

---

## Phase 5 — Review et documentation

| Tâche | Description | Statut |
|-------|-------------|--------|
| 5.1 | Audit sécurité | ⏳ |
| 5.2 | Code review | ⏳ |
| 5.3 | `README.md` complet | ⏳ |

**Jalon 5** : Projet livrable, dépôt public.

---

## Problèmes ouverts

| # | Problème | Impact | Status |
|---|----------|--------|--------|
| P1 | mock_server.py se lie à localhost mais config.py utilise `raspberrypi.local` — connexion échoue sans configuration hosts | Test Phase 4 sans Pi réel | À documenter dans README |
| P2 | G-code demo.nc devrait être dans `sentinelle/` ou `data/` au lieu de racine | Organisation | Optionnel |

---

## Récapitulatif des jalons

| Jalon | Critère | Statut | Date |
|-------|---------|--------|------|
| Jalon 0 | Fondations (config, protocol, state) | ✅ | 2026-04-14 |
| Jalon 1A | Pilier acoustique Pi fonctionnel | ✅ | 2026-04-15 |
| Jalon 1B | Composants laptop purs | ✅ | 2026-04-15 |
| Jalon 2 | 51 tests verts | ✅ | 2026-04-15 |
| **Jalon 3** | **Démo visuelle complète** | **✅** | **2026-04-16** |
| Jalon 4 | Tests hardware + vidéo | ⏳ | — |
| Jalon 5 | Projet livrable | ⏳ | — |

---

## Historique des commits (branche phase3)

```
b8255d3 Corrige palpitations webcam dans _draw_webcam_preview()
6c367dc Met à jour ROADMAP.md — Jalon 3 atteint
2b259ac Ajoute T-3.4 main_laptop.py avec CLI et logging JSONL
b819e69 Ajoute T-3.3-ter bouton MUTE 30s + compteur faux positifs
92f7fcd Ajoute T-3.3-bis bouton BASELINE avec barre de progression
e5a5b52 Ajoute T-3.3 intégration pilier acoustique
0b7906b Ajoute T-3.2 intégration pilier visuel
3098617 Ajoute T-3.1 simulateur pygame split-screen
1202004 Ajoute TODOs critiques S0 pour Phase 3
```

**Mis à jour le 2026-04-16** — Phase 3 complète ✅ | 8 commits | 51 tests verts | Démo visuelle fonctionnelle
