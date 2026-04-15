"""Adapter sounddevice → queue interne.

Capture audio via sounddevice et alimente une queue de blocs audio
pour traitement par l'analyseur.
"""

from __future__ import annotations

import queue
import threading
from typing import Callable

import numpy as np
import sounddevice as sd

from sentinelle import config


class AudioCapture:
    """Audio capture adapter using sounddevice.

    Captures audio in a background thread and feeds blocks
    to an internal queue for processing.

    Attributes:
        queue: Queue of audio blocks (numpy arrays).
        is_running: True if capture is active.
    """

    def __init__(
        self,
        queue_maxsize: int = 100,
        device: int | None = None,
    ) -> None:
        self.queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=queue_maxsize)
        self.is_running: bool = False
        self._device = device
        self._stream: sd.InputStream | None = None
        self._lock = threading.Lock()

    def _callback(
        self,
        indata: np.ndarray,
        frames: int,
        time_info: dict,
        status: sd.CallbackFlags,
    ) -> None:
        """Sounddevice callback — push audio block to queue."""
        if status:
            pass  # Log status if needed
        audio_block = indata[:, 0].copy()  # Mono
        try:
            self.queue.put_nowait(audio_block)
        except queue.Full:
            pass  # Drop oldest block

    def start(self) -> None:
        """Start audio capture."""
        with self._lock:
            if self.is_running:
                return
            self._stream = sd.InputStream(
                samplerate=config.AUDIO_SR,
                blocksize=config.AUDIO_BLOCKSIZE,
                channels=1,
                callback=self._callback,
                device=self._device,
            )
            self._stream.start()
            self.is_running = True

    def stop(self) -> None:
        """Stop audio capture."""
        with self._lock:
            if not self.is_running:
                return
            if self._stream:
                self._stream.stop()
                self._stream.close()
                self._stream = None
            self.is_running = False

    def get_block(self, timeout: float = 1.0) -> np.ndarray | None:
        """Get next audio block from queue.

        Args:
            timeout: Max seconds to wait for a block.

        Returns:
            Audio block as numpy array, or None if timeout.
        """
        try:
            return self.queue.get(timeout=timeout)
        except queue.Empty:
            return None