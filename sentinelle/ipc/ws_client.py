"""Client WebSocket daemon — reçoit les événements acoustiques du Pi.

Thread daemon avec boucle asyncio interne. Communication avec le thread
principal (pygame) exclusivement via queue.Queue().

Ne jamais appeler ce code depuis le thread pygame directement.
"""

from __future__ import annotations

import asyncio
import logging
import threading
from queue import Empty, Full, Queue

import websockets

from sentinelle import config
from sentinelle.protocol import AcousticEvent, InvalidProtocolMessage, from_json

logger = logging.getLogger(__name__)


class AcousticLink:
    """Client WebSocket daemon pour les événements acoustiques.

    Se connecte au serveur WebSocket du Pi, parse les messages entrants
    selon le protocole défini dans protocol.py, et les push dans une
    queue thread-safe pour consommation par la boucle pygame.

    Attributes:
        _queue: Queue thread-safe (maxsize=50). Drop events si pleine.
        _thread: Thread daemon exécutant la boucle asyncio.
        _stop_event: Signal d'arrêt pour le thread.
        _host: Hôte WebSocket (config.WS_HOST).
        _port: Port WebSocket (config.WS_PORT).
    """

    def __init__(
        self,
        host: str | None = None,
        port: int | None = None,
    ) -> None:
        """Initialise le client WebSocket.

        Args:
            host: Hôte WebSocket. Par défaut config.WS_HOST.
            port: Port WebSocket. Par défaut config.WS_PORT.
        """
        self._queue: Queue[AcousticEvent | dict] = Queue(maxsize=50)
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._host = config.WS_HOST if host is None else host
        self._port = config.WS_PORT if port is None else port

    def start(self) -> None:
        """Démarre le thread daemon de connexion WebSocket.

        Non-bloquant — le thread se connecte en arrière-plan.
        Sans effet si déjà démarré.
        """
        if self._thread is not None and self._thread.is_alive():
            return

        self._stop_event.clear()
        self._thread = threading.Thread(
            target=self._run_loop,
            daemon=True,
            name="acoustic-link",
        )
        self._thread.start()

    def stop(self) -> None:
        """Signale l'arrêt du thread daemon.

        Non-bloquant — le thread s'arrête au prochain cycle de reconnexion.
        """
        self._stop_event.set()

    def get_event(self) -> AcousticEvent | dict | None:
        """Lit le prochain événement de la queue (non-bloquant).

        Returns:
            AcousticEvent si un événement acoustique valide est disponible,
            dict de status {"type": "status", "connected": bool} si le
            statut de connexion a changé, ou None si la queue est vide.
        """
        try:
            return self._queue.get_nowait()
        except Empty:
            return None

    def _run_loop(self) -> None:
        """Boucle principale du thread daemon — exécute l'event loop asyncio."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            loop.run_until_complete(self._connect_loop())
        finally:
            loop.close()

    async def _connect_loop(self) -> None:
        """Boucle de reconnexion avec backoff exponentiel."""
        backoff_sequence = list(config.WS_RECONNECT_BACKOFF)
        max_backoff = backoff_sequence[-1]
        attempt = 0

        while not self._stop_event.is_set():
            uri = f"ws://{self._host}:{self._port}"
            try:
                await self._run_session(uri)
                attempt = 0  # Reset backoff after clean session
            except (ConnectionRefusedError, OSError, websockets.exceptions.WebSocketException) as exc:
                logger.warning("WebSocket connection lost: %s", exc)
                self._push_status(False)
            except Exception as exc:  # noqa: BLE001
                # Unexpected exception (bug in handler, MemoryError, etc.) — log and
                # re-enter the backoff loop so the daemon thread never dies silently.
                logger.error("Unexpected error in connect loop: %s", exc, exc_info=True)
                self._push_status(False)

            if self._stop_event.is_set():
                break

            # Calculate backoff
            if attempt < len(backoff_sequence):
                delay = backoff_sequence[attempt]
            else:
                delay = max_backoff
            attempt += 1

            logger.info("Reconnecting in %ds (attempt %d)...", delay, attempt)

            await asyncio.sleep(delay)

            if self._stop_event.is_set():
                break

    async def _run_session(self, uri: str) -> None:
        """Session WebSocket connectée — reçoit et parse les messages."""
        async with websockets.connect(uri) as websocket:
            self._push_status(True)
            try:
                async for raw_message in websocket:
                    if self._stop_event.is_set():
                        break

                    try:
                        event = from_json(raw_message)
                        self._push_event(event)
                    except InvalidProtocolMessage as exc:
                        logger.warning("Invalid protocol message: %s", exc)
                        # Continue processing — don't crash on bad messages
            finally:
                if not self._stop_event.is_set():
                    self._push_status(False)

    def _push_event(self, event: AcousticEvent) -> None:
        """Push un événement acoustique dans la queue (non-bloquant).

        Drop silencieusement si la queue est pleine pour ne pas bloquer
        le thread de réception.
        """
        try:
            self._queue.put_nowait(event)
        except Full:
            # Queue pleine — drop l'événement pour ne pas bloquer
            logger.debug("Event queue full, dropping event")

    def _push_status(self, connected: bool) -> None:
        """Push un événement de statut de connexion dans la queue."""
        try:
            self._queue.put_nowait({"type": "status", "connected": connected})
        except Full:
            logger.debug("Event queue full, dropping status event")
