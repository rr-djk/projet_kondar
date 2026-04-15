---
status: todo
type: feature
priority: high
assigned_to: implementation-specialist
started_at: null
depends_on: [T-0.3]
files_touched: [sentinelle/ipc/mock_server.py]
related_to: null
---

# T-1B.5 — mock_server.py (émetteur acoustique)

## Description
Serveur WebSocket simple qui émet des événements acoustiques synthétiques
(warn/critical) sur ws://localhost:8765 pour tester Lane C sans Pi physique.

## Spécifications
- asyncio WebSocket server sur `WS_PORT` (8765) depuis `config.py`
- Émet événements `AcousticEvent` valides selon `protocol.py`
- Alterne warn/critical à intervalle régulier (~2s)
- Utilise `protocol.to_json()` pour la sérialisation
- CLI : `python -m sentinelle.ipc.mock_server`
- Arrêt propre avec Ctrl+C

## Critères d'acceptation
- Importable et exécutable sans erreur
- Émet des événements JSON valides selon le schéma protocol.py
- Client WebSocket peut se connecter et recevoir les events
- Débloque Lane C sans besoin du Pi physique
