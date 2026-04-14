# ARCHITECTURE.md — SENTINELLE CNC

Généré par `/plan-eng-review` le 2026-04-13.
Commit de référence : `e56e8e9`

**Lire aussi :** `DESIGN.md` (vision produit, problem statement, prémisses, critères de succès)

---

## Vue d'ensemble

SENTINELLE CNC est un copilote d'autonomie machine pour opérateurs CNC. Deux piliers
indépendants qui tournent en parallèle, réunis dans une interface unifiée.

```
┌─────────────────────────────────────────────────────────┐
│                   RASPBERRY PI 4                         │
│                                                          │
│  sounddevice callback                                    │
│      │                                                   │
│      ▼                                                   │
│  [acoustic/capture.py]  ←── micro USB ou MAX9814         │
│      │  blocs audio (blocksize=4096, ~93ms @ 44.1kHz)   │
│      ▼                                                   │
│  [acoustic/analyzer.py]                                  │
│      │  FFT glissante (fenêtre 512ms, overlap 50%)       │
│      │  baseline = moyenne magnitudes sur 10s            │
│      │  anomalie = crête ≥ baseline + 2σ                 │
│      ▼                                                   │
│  [acoustic/server.py]  ─── asyncio WebSocket server      │
│      │  ws://raspberrypi.local:8765                      │
│      │  {"type":"acoustic","severity":"warn|critical",   │
│      │   "ts":<epoch_ms>}                                │
└──────┼──────────────────────────────────────────────────┘
       │ LAN (~5-20ms)
       ▼
┌─────────────────────────────────────────────────────────┐
│                      LAPTOP                              │
│                                                          │
│  Thread daemon : asyncio WebSocket client                │
│      │  reçoit events Pi → queue.Queue()                │
│      │                                                   │
│  Thread principal : boucle pygame @ 60fps               │
│      │  lit queue.Queue() à chaque frame (non-bloquant) │
│      │                                                   │
│  [visual/obstacle.py]  ←── webcam USB                   │
│      │  masque HSV (orange : H:5-25, S:100+, V:100+)    │
│      │  fallback : ArUco markers                         │
│      │  bounding box → coordonnées grille 50×50         │
│      ▼                                                   │
│  [visual/gcode_parser.py]                                │
│      │  parse G0/G1 depuis fichier .nc                  │
│      │  coordonnées mm → pixels via config.py           │
│      ▼                                                   │
│  [visual/planner.py]                                     │
│      │  A* sur grille 50×50                             │
│      │  recalcul < 200ms, max 5Hz                       │
│      │  si aucun chemin → None → pause + overlay        │
│      ▼                                                   │
│  [visual/simulator.py]  ──── pygame split-screen        │
│      │  gauche : simulateur visuel                       │
│      │  droite  : graphe FFT + alertes acoustiques       │
│      │  overlay rouge si acoustic.severity="critical"    │
│      │  overlay "CHEMIN IMPOSSIBLE" si A* retourne None  │
│      │  badge "ACOUSTIC OFFLINE" si WebSocket déconnecté │
└─────────────────────────────────────────────────────────┘
```

---

## Structure de fichiers (V1)

```
sentinelle/
├── config.py              # Constantes globales
├── protocol.py            # Schéma IPC partagé Pi/laptop (AcousticEvent, to_json, from_json)
├── state.py               # FSM AppState — enum + transition(event)
├── acoustic/
│   ├── capture.py         # Adapter sounddevice → queue interne
│   ├── analyzer.py        # Fonctions pures : fft, detect_anomaly(spectrum, baseline)
│   ├── baseline.py        # BaselineStore — état mutable isolé (compute + sanity check)
│   └── server.py          # asyncio WebSocket server (port 8765)
├── visual/
│   ├── gcode_parser.py    # parse G0/G1 → List[Segment]
│   ├── obstacle.py        # HSV detection → BoundingBox | None
│   ├── planner.py         # A* grille 50×50 → List[Point] | None (timeout 150ms)
│   └── simulator.py       # pygame loop — orchestration UI uniquement
├── ipc/
│   └── ws_client.py       # AcousticLink : thread daemon + queue.Queue (reconnect backoff)
├── main_pi.py             # Entry point Pi
├── main_laptop.py         # Entry point laptop
└── tests/
    ├── test_analyzer.py
    ├── test_gcode_parser.py
    ├── test_planner.py
    ├── test_obstacle.py
    ├── test_protocol.py   # round-trip JSON, schéma contractuel
    └── test_state.py      # transitions FSM
```

**Pi :** `python main_pi.py`
**Laptop :** `python main_laptop.py demo.nc [--camera N]`

**Principe :** `analyzer.py` et `planner.py` sont des fonctions pures sans état. L'état mutable vit dans `baseline.py` et `state.py`. Les adapters I/O (`capture.py`, `obstacle.py`, `ws_client.py`) sont les seuls à parler au hardware.

---

## config.py — Constantes à connaître

```python
WORKSPACE_MM = (300, 200)   # Espace de travail simulé en mm
GRID_SIZE = (50, 50)        # Grille A*
AUDIO_SR = 44100            # Sample rate audio
FFT_WINDOW_MS = 512         # Fenêtre FFT en ms
FFT_OVERLAP = 0.5           # Overlap 50%
AUDIO_BLOCKSIZE = 4096      # Blocs sounddevice (~93ms)
BASELINE_DURATION_S = 10      # Durée capture baseline
ANOMALY_WARN_SIGMA = 2.0      # Seuil warn (alerte jaune)
ANOMALY_CRITICAL_SIGMA = 3.0  # Seuil critical (overlay rouge + pause)
WS_HOST = "raspberrypi.local"
WS_PORT = 8765
WS_RECONNECT_BACKOFF = [1, 2, 5]  # secondes, plafonné à 5s
HSV_ORANGE_LOW = (5, 100, 100)
HSV_ORANGE_HIGH = (25, 255, 255)
CAMERA_INDEX = 0              # Changer selon la machine, override avec --camera N
```

---

## Décisions d'architecture (prises en review)

| Décision | Choix retenu | Alternative rejetée | Raison |
|---|---|---|---|
| Concurrence laptop | Thread daemon + `queue.Queue` | nest_asyncio | Race conditions sous charge |
| Audio library Pi | `sounddevice` | `pyaudio` | Installation ARM fiable |
| Mapping G-code | `config.py` WORKSPACE_MM | Auto-détect depuis .nc | Fragilité valeurs extrêmes |
| A* no-path | Pause + overlay "CHEMIN IMPOSSIBLE" | Continuer trajectoire originale | Comportement sécuritaire |

---

## Schéma de message WebSocket

```json
// Pilier acoustique (Pi → Laptop)
{"type": "acoustic", "severity": "warn|critical", "ts": 1713000000000}

// État connexion (Thread WebSocket → queue interne)
{"type": "status", "connected": true|false}

// Pilier visuel (interne, loggé)
{"type": "vision", "obstacle": true, "replanned": true, "ts": 1713000000000}
```

---

## Parallelisation d'implémentation

Trois lanes indépendantes. A + B peuvent être buildes en parallèle.

```
Lane A (Pi)         Lane B (Laptop, no hardware)    Lane C (intégration)
──────────          ──────────────────────────      ─────────────────────
acoustic/           visual/gcode_parser.py          visual/simulator.py
  capture.py        visual/obstacle.py              main.py
  analyzer.py       visual/planner.py               WebSocket IPC
  server.py
                                                    Dépend de A + B stables
```

---

## Tests requis (tous fonctions pures, sans hardware)

| Fichier | Test | Type |
|---|---|---|
| `acoustic/analyzer.py` | baseline normale, anomalie détectée, limite 1.9σ, buffer partiel | pytest |
| `visual/gcode_parser.py` | G0+G1 valides, fichier vide, lignes non-G-code ignorées | pytest |
| `visual/planner.py` | chemin libre, contournement obstacle, aucun chemin → None | pytest |
| `visual/obstacle.py` | image orange synthétique → BoundingBox, image grise → None | pytest |
| IPC schema | message JSON acoustique parsé correctement | pytest |

Détail complet dans le test plan :
`~/.gstack/projects/rr-djk-projet_kondar/rr-djk-main-eng-review-test-plan-*.md`

---

## Décisions ouvertes — tranchées le 2026-04-14

| # | Question | Décision |
|---|---|---|
| Q1 | Acquittement alerte acoustique V1 | Pause auto du simulateur après 3s + touche `Espace` pour reprendre. Simule E-stop sans GPIO. |
| Q2 | Re-baseline une fois RUNNING | Bouton désactivé en `RUNNING`. Badge "Baseline active" affiché. Redémarrer l'app pour recapturer. |
| Q3 | Chargement G-code | Argument CLI : `python main_laptop.py demo.nc`. Pas de file picker en V1. |
| Q4 | Seuils warn/critical | `ANOMALY_WARN_SIGMA = 2.0` → alerte jaune. `ANOMALY_CRITICAL_SIGMA = 3.0` → overlay rouge + pause. Les deux dans `config.py`. |
| Q5 | Logging `.jsonl` | Logger synchrone dans boucle principale. Uniquement les transitions FSM, alertes et obstacles (pas chaque frame). Fichier `session_<ts>.jsonl`. |
| Q6 | Index webcam | `CAMERA_INDEX = 0` dans `config.py` + override CLI `--camera N`. Pas d'auto-detect (comportement imprévisible sur hardware multiple). |
| Q7 | Overlays simultanés ALERT_CRITICAL + PATH_BLOCKED | Panels indépendants. Panel droit rouge (acoustique). Panel gauche garde "CHEMIN IMPOSSIBLE". Deux flags indépendants dans la FSM : `acoustic_alert`, `path_blocked`. |

---

## Gaps critiques (TODOS.md)

1. **Bouton "Démarrer baseline"** : baseline ne doit pas se capturer automatiquement au
   lancement. Si la machine tourne déjà en conditions anormales, la baseline est corrompue.
   Fix : bouton explicite dans l'UI, état `baseline_ready: bool`.

2. **Badge "ACOUSTIC OFFLINE"** : si le Pi n'est pas joignable, afficher un indicateur
   visible plutôt que silence. Fix : event `{"type":"status","connected":false}` si
   WebSocket timeout après 5s.

---

## NOT in scope (V1)

- Gradual tool wear detection (multi-runs, modèle de tendance)
- Intégration CNC physique GRBL (V2, contrôleur requis)
- Enclosure 3D imprimée
- Packaging pip / Docker
- GUI de configuration (config.py suffit)
- Calibration acoustique multi-matériaux

---

## Review Readiness Dashboard

```
+====================================================================+
|                    REVIEW READINESS DASHBOARD                       |
+====================================================================+
| Review          | Runs | Last Run            | Status    | Required |
|-----------------|------|---------------------|-----------|----------|
| Eng Review      |  1   | 2026-04-14 03:36    | CLEAR     | YES      |
| CEO Review      |  0   | —                   | —         | no       |
| Design Review   |  0   | —                   | —         | no       |
| Adversarial     |  0   | —                   | —         | no       |
| Outside Voice   |  0   | —                   | —         | no       |
+--------------------------------------------------------------------+
| VERDICT: CLEARED — Eng Review passé. Commit e56e8e9                |
+====================================================================+
```
