"""Serveur WebSocket mock — émet des événements acoustiques synthétiques.

Permet de tester l'intégration Lane C sans le Pi physique.
Émet des événements AcousticEvent valides selon protocol.py.

Usage :
    python -m sentinelle.ipc.mock_server
    python sentinelle/ipc/mock_server.py
"""

from __future__ import annotations

import asyncio
import logging
import signal
import time

import websockets

from sentinelle import config
from sentinelle.protocol import AcousticEvent, to_json

logger = logging.getLogger(__name__)

# Intervalle entre l'émission d'événements (secondes)
_EMIT_INTERVAL_S = 2.0


async def _emit_events(websocket: websockets.WebSocketServerProtocol) -> None:
    """Émet des événements warn/critical en alternance sur la connexion.

    Args:
        websocket: Connexion WebSocket du client connecté.
    """
    severities = ["warn", "critical"]
    index = 0

    while True:
        severity = severities[index % len(severities)]
        event = AcousticEvent(
            type="acoustic",
            severity=severity,  # type: ignore[arg-type]
            ts=int(time.time() * 1000),
        )
        message = to_json(event)
        await websocket.send(message)
        logger.info("Émis: %s", message)

        index += 1
        await asyncio.sleep(_EMIT_INTERVAL_S)


async def _handler(websocket: websockets.WebSocketServerProtocol) -> None:
    """Gère une connexion client entrante."""
    logger.info("Client connecté depuis %s", websocket.remote_address)
    try:
        await _emit_events(websocket)
    except websockets.exceptions.ConnectionClosed:
        logger.info("Client déconnecté")


async def _run_server(host: str, port: int) -> None:
    """Démarre le serveur WebSocket et attend les connexions.

    Args:
        host: Adresse d'écoute (par défaut "localhost").
        port: Port d'écoute (par défaut config.WS_PORT).
    """
    loop = asyncio.get_running_loop()
    stop = loop.create_future()

    # Handle Ctrl+C gracefully
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set_result, None)

    async with websockets.serve(_handler, host, port):
        logger.info("Mock server démarré sur ws://%s:%d", host, port)
        logger.info("Ctrl+C pour arrêter")
        await stop


def main(host: str = "localhost", port: int | None = None) -> None:
    """Point d'entrée du serveur mock.

    Args:
        host: Adresse d'écoute. Par défaut "localhost".
        port: Port d'écoute. Par défaut config.WS_PORT.
    """
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    target_port = port or config.WS_PORT
    asyncio.run(_run_server(host, target_port))


if __name__ == "__main__":
    main()
