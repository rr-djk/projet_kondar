"""Tests du client WebSocket daemon — ws_client.py.

Couvre (T-2.7) :
  1. Event parsing valide : serveur envoie JSON valide → AcousticEvent reçu dans la queue
  2. Reconnect après coupure : serveur absent au démarrage → client reconnecte quand dispo
  3. Queue non-bloquante : 51 events pushés → drop silencieux, pas de crash
  4. InvalidProtocolMessage catché : serveur envoie JSON invalide → pas de crash

Zéro Pi — tous les serveurs sont locaux (localhost).
"""

import asyncio
import socket
import threading
import time

import pytest
import websockets

from sentinelle import config
from sentinelle.ipc.ws_client import AcousticLink
from sentinelle.protocol import AcousticEvent, to_json


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_free_port() -> int:
    """Retourne un port TCP libre sur localhost."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("localhost", 0))
        return s.getsockname()[1]


def _start_server(port: int, handler, started: threading.Event) -> threading.Thread:
    """Démarre un serveur WebSocket asyncio dans un thread daemon.

    Args:
        port: Port d'écoute.
        handler: Coroutine handler(websocket) à appeler à chaque connexion.
        started: Event signalé quand le serveur est prêt.

    Returns:
        Thread daemon (déjà démarré).
    """

    async def serve() -> None:
        async with websockets.serve(handler, "localhost", port):
            started.set()
            await asyncio.sleep(5)  # Sert pendant 5s puis se ferme

    def run() -> None:
        asyncio.run(serve())

    t = threading.Thread(target=run, daemon=True)
    t.start()
    return t


def _drain_queue(link: AcousticLink) -> list:
    """Vide la queue de l'AcousticLink et retourne les items collectés."""
    items = []
    while True:
        item = link.get_event()
        if item is None:
            break
        items.append(item)
    return items


def _wait_for_event(link: AcousticLink, timeout: float = 3.0) -> AcousticEvent | None:
    """Attend le premier AcousticEvent dans la queue avec un timeout."""
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        item = link.get_event()
        if isinstance(item, AcousticEvent):
            return item
        time.sleep(0.05)
    return None


# ---------------------------------------------------------------------------
# Test 1 : event parsing valide
# ---------------------------------------------------------------------------


def test_valid_event_received():
    """AcousticLink reçoit et parse correctement un événement warn depuis un serveur local."""
    port = _get_free_port()
    event_to_send = AcousticEvent(type="acoustic", severity="warn", ts=1_713_000_000_000)
    msg = to_json(event_to_send)

    async def handler(ws):
        await ws.send(msg)
        await asyncio.sleep(3)  # Maintient la connexion ouverte

    started = threading.Event()
    _start_server(port, handler, started)
    assert started.wait(timeout=3), "Serveur local n'a pas démarré"

    link = AcousticLink(host="localhost", port=port)
    link.start()

    received = _wait_for_event(link, timeout=3.0)
    link.stop()

    assert received is not None
    assert isinstance(received, AcousticEvent)
    assert received.severity == "warn"
    assert received.ts == 1_713_000_000_000


# ---------------------------------------------------------------------------
# Test 2 : reconnect après coupure initiale
# ---------------------------------------------------------------------------


def test_reconnect_after_initial_failure():
    """AcousticLink reconnecte quand le serveur devient disponible après un échec initial.

    Scénario :
      1. AcousticLink démarre alors qu'aucun serveur n'écoute → échec ConnectionRefused
      2. Le serveur démarre (avec backoff court patché)
      3. Le client reconnecte et reçoit un événement
    """
    port = _get_free_port()
    event_to_send = AcousticEvent(type="acoustic", severity="critical", ts=1_713_000_000_002)
    msg = to_json(event_to_send)

    # Patch du backoff pour accélérer la reconnexion (0.1s au lieu de [1,2,5]s)
    original_backoff = config.WS_RECONNECT_BACKOFF
    config.WS_RECONNECT_BACKOFF = (0.1, 0.1, 0.1)

    try:
        # 1. Démarrer le client AVANT le serveur
        link = AcousticLink(host="localhost", port=port)
        link.start()
        time.sleep(0.2)  # Laisser le client échouer une fois

        # 2. Démarrer le serveur
        async def handler(ws):
            await ws.send(msg)
            await asyncio.sleep(3)

        started = threading.Event()
        _start_server(port, handler, started)
        assert started.wait(timeout=3), "Serveur local n'a pas démarré"

        # 3. Attendre la reconnexion et la réception de l'événement
        received = _wait_for_event(link, timeout=5.0)
        link.stop()

    finally:
        config.WS_RECONNECT_BACKOFF = original_backoff

    assert received is not None
    assert received.severity == "critical"


# ---------------------------------------------------------------------------
# Test 3 : queue non-bloquante (maxsize=50)
# ---------------------------------------------------------------------------


def test_queue_full_drops_silently():
    """Pousser 51 events dans une queue de maxsize=50 ne lève pas d'exception.

    Le 51ème event est silencieusement droppé.
    """
    link = AcousticLink(host="localhost", port=_get_free_port())

    event = AcousticEvent(type="acoustic", severity="warn", ts=1_713_000_000_000)

    # Remplir la queue jusqu'à la capacité maximale
    for _ in range(50):
        link._push_event(event)

    # Le 51ème drop ne doit pas lever d'exception
    link._push_event(event)  # silently dropped

    # La queue contient exactement 50 éléments
    items = _drain_queue(link)
    assert len(items) == 50


# ---------------------------------------------------------------------------
# Test 4 : InvalidProtocolMessage catché sans crash
# ---------------------------------------------------------------------------


def test_invalid_protocol_message_no_crash():
    """Un message JSON invalide du serveur est loggué en warning — pas de crash.

    Le client continue de fonctionner et aucun AcousticEvent invalide
    n'est ajouté à la queue.
    """
    port = _get_free_port()

    # Serveur qui envoie un JSON malformé (champs manquants)
    async def handler(ws):
        await ws.send('{"type": "acoustic"}')  # manque severity et ts
        await asyncio.sleep(3)

    started = threading.Event()
    _start_server(port, handler, started)
    assert started.wait(timeout=3), "Serveur local n'a pas démarré"

    link = AcousticLink(host="localhost", port=port)
    link.start()

    # Attendre assez pour que le message soit traité
    time.sleep(0.5)
    link.stop()

    # Vider la queue : aucun AcousticEvent ne doit être présent
    items = _drain_queue(link)
    acoustic_events = [i for i in items if isinstance(i, AcousticEvent)]
    assert len(acoustic_events) == 0
