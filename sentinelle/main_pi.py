"""Entry point pour Raspberry Pi.

Orchestre la capture audio, l'analyse FFT, la baseline
et l'envoi d'événements via WebSocket.
"""

from __future__ import annotations

import asyncio
import logging
import time

import numpy as np

from sentinelle import config
from sentinelle.acoustic.analyzer import compute_fft, detect_anomaly_from_energy
from sentinelle.acoustic.baseline import BaselineStore
from sentinelle.acoustic.capture import AudioCapture
from sentinelle.acoustic.server import run_server
from sentinelle.protocol import AcousticEvent

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def capture_baseline(
    capture: AudioCapture,
    store: BaselineStore,
    duration_s: float = config.BASELINE_DURATION_S,
) -> None:
    """Capture audio for baseline computation.

    Args:
        capture: Audio capture adapter.
        store: BaselineStore to collect spectra.
        duration_s: Duration of baseline capture in seconds.
    """
    start = time.monotonic()
    while time.monotonic() - start < duration_s:
        block = await asyncio.to_thread(capture.get_block, 1.0)
        if block is not None:
            spectrum = compute_fft(block)
            store.add_spectrum(spectrum)
    store.compute()
    logger.info(
        "Baseline computed: mean=%.2f, std=%.2f",
        store.baseline_mean,
        store.baseline_std,
    )


async def monitor_loop(
    capture: AudioCapture,
    store: BaselineStore,
    event_queue: asyncio.Queue[AcousticEvent],
) -> None:
    """Main monitoring loop — analyze audio and emit events.

    Args:
        capture: Audio capture adapter.
        store: BaselineStore with computed baseline.
        event_queue: Queue to push acoustic events.
    """
    while True:
        block = await asyncio.to_thread(capture.get_block, 1.0)
        if block is None:
            continue

        spectrum = compute_fft(block)
        energy = float(np.sum(spectrum))

        severity = detect_anomaly_from_energy(
            energy,
            store.baseline_mean,
            store.baseline_std,
        )

        if severity is not None:
            event = AcousticEvent(
                type="acoustic",
                severity=severity,
                ts=int(time.time() * 1000),
            )
            try:
                event_queue.put_nowait(event)
                logger.info("Anomaly detected: %s", severity)
            except asyncio.QueueFull:
                logger.warning("Event queue full, dropping %s event", severity)


async def main() -> None:
    """Main entry point for Raspberry Pi."""
    logger.info("Starting SENTINELLE CNC — Pi node")

    capture = AudioCapture()
    store = BaselineStore()
    event_queue: asyncio.Queue[AcousticEvent] = asyncio.Queue(maxsize=50)

    capture.start()
    logger.info("Audio capture started")

    try:
        # Capture baseline
        logger.info("Capturing baseline for %ds...", config.BASELINE_DURATION_S)
        await capture_baseline(capture, store)

        if not store.sanity_check():
            logger.error("Baseline sanity check failed — aborting")
            return

        # Start monitoring + server
        monitor_task = asyncio.create_task(monitor_loop(capture, store, event_queue))
        try:
            await run_server(event_queue)
        except asyncio.CancelledError:
            logger.info("Shutting down...")
        finally:
            monitor_task.cancel()
    finally:
        capture.stop()


if __name__ == "__main__":
    asyncio.run(main())