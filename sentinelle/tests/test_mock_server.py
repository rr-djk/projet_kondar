"""Tests du serveur mock WebSocket — mock_server.py.

Couvre (T-2.8) :
  1. Le serveur émet des events JSON valides conformes à protocol.py
  2. Le serveur alterne warn/critical (séquence correcte)

Utilise asyncio.run() dans des tests synchrones — zéro Pi, zéro hardware.
"""

import asyncio
import socket

import websockets

import sentinelle.ipc.mock_server as mock_server_module
from sentinelle.protocol import AcousticEvent, from_json


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_free_port() -> int:
    """Retourne un port TCP libre sur localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


def _receive_n_messages(port: int, n: int, interval: float = 0.05) -> list[str]:
    """Connecte au mock server et collecte n messages.

    Args:
        port: Port d'écoute du serveur.
        n: Nombre de messages à collecter.
        interval: Intervalle d'émission mocké (secondes).

    Returns:
        Liste de n messages JSON bruts (str).
    """
    messages: list[str] = []

    # Patch l'intervalle pour accélérer le test
    original = mock_server_module._EMIT_INTERVAL_S
    mock_server_module._EMIT_INTERVAL_S = interval

    async def run() -> None:
        async with websockets.serve(mock_server_module._handler, "localhost", port):
            async with websockets.connect(f"ws://localhost:{port}") as ws:
                for _ in range(n):
                    msg = await asyncio.wait_for(ws.recv(), timeout=3.0)
                    messages.append(msg)

    try:
        asyncio.run(run())
    finally:
        mock_server_module._EMIT_INTERVAL_S = original

    return messages


# ---------------------------------------------------------------------------
# Test 1 : events JSON valides
# ---------------------------------------------------------------------------


def test_emits_valid_json_events():
    """Le mock server émet des events JSON valides conformes à protocol.py."""
    port = _get_free_port()
    messages = _receive_n_messages(port, n=1)

    assert len(messages) == 1
    event = from_json(messages[0])  # lève InvalidProtocolMessage si invalide

    assert isinstance(event, AcousticEvent)
    assert event.type == "acoustic"
    assert event.severity in ("warn", "critical")
    assert event.ts > 0


# ---------------------------------------------------------------------------
# Test 2 : alternance warn/critical
# ---------------------------------------------------------------------------


def test_alternates_warn_critical():
    """Le mock server alterne warn puis critical sur les deux premiers events."""
    port = _get_free_port()
    messages = _receive_n_messages(port, n=2)

    assert len(messages) == 2
    events = [from_json(m) for m in messages]
    severities = [e.severity for e in events]

    # Premier événement : "warn", second : "critical"
    assert severities[0] == "warn"
    assert severities[1] == "critical"
