"""Asyncio WebSocket server pour le Pi.

Écoute sur le port 8765 et envoie les événements acoustiques
au laptop connecté.
"""

from __future__ import annotations

import asyncio
import logging
import time

import websockets

from sentinelle import config
from sentinelle.protocol import AcousticEvent, to_json

logger = logging.getLogger(__name__)


class AcousticServer:
    """WebSocket server that broadcasts acoustic events to connected clients.

    Attributes:
        host: Server host (default from config).
        port: Server port (default from config).
    """

    def __init__(
        self,
        host: str = config.WS_HOST,
        port: int = config.WS_PORT,
    ) -> None:
        self.host = host
        self.port = port
        self._clients: set[websockets.ServerConnection] = set()
        self._server: websockets.WebSocketServerProtocol | None = None

    async def emit(self, event: AcousticEvent) -> None:
        """Send an acoustic event to all connected clients.

        Args:
            event: The acoustic event to send.
        """
        message = to_json(event)
        if not self._clients:
            return
        await asyncio.gather(
            *[client.send(message) for client in self._clients],
            return_exceptions=True,
        )

    async def _handler(self, websocket: websockets.ServerConnection) -> None:
        """Handle a single WebSocket connection."""
        self._clients.add(websocket)
        logger.info("Client connected: %s", websocket.remote_address)
        try:
            await websocket.wait_closed()
        finally:
            self._clients.discard(websocket)
            logger.info("Client disconnected: %s", websocket.remote_address)

    async def start(self) -> None:
        """Start the WebSocket server."""
        async with websockets.serve(self._handler, self.host, self.port) as server:
            logger.info("Acoustic server listening on ws://%s:%d", self.host, self.port)
            self._server = server
            await asyncio.Future()  # Run forever

    def stop(self) -> None:
        """Stop the WebSocket server."""
        if self._server:
            self._server.close()
            logger.info("Acoustic server stopped")


async def run_server(
    event_queue: asyncio.Queue[AcousticEvent],
    host: str = config.WS_HOST,
    port: int = config.WS_PORT,
) -> None:
    """Run the acoustic server, emitting events from a queue.

    Args:
        event_queue: Asyncio queue of acoustic events to emit.
        host: Server host.
        port: Server port.
    """
    server = AcousticServer(host=host, port=port)

    async def _emit_loop() -> None:
        while True:
            event = await event_queue.get()
            await server.emit(event)
            event_queue.task_done()

    emit_task = asyncio.create_task(_emit_loop())
    try:
        await server.start()
    finally:
        emit_task.cancel()