"""BaselineStore — état mutable isolé pour la capture de baseline.

Gère la collecte des spectres FFT pendant la phase de baseline
et calcule les statistiques de référence.
"""

from __future__ import annotations

import numpy as np

from sentinelle import config
from sentinelle.acoustic.analyzer import compute_baseline


class BaselineStore:
    """Mutable state for baseline capture.

    Collects spectra during baseline phase and computes
    baseline statistics (mean, std).

    Attributes:
        spectra: List of collected magnitude spectra.
        baseline_mean: Computed mean energy (None until computed).
        baseline_std: Computed standard deviation (None until computed).
        is_ready: True if baseline has been computed successfully.
    """

    def __init__(self) -> None:
        self.spectra: list[np.ndarray] = []
        self.baseline_mean: float | None = None
        self.baseline_std: float | None = None
        self.is_ready: bool = False

    def add_spectrum(self, spectrum: np.ndarray) -> None:
        """Add a spectrum to the baseline collection.

        Args:
            spectrum: Magnitude spectrum from analyzer.compute_fft.
        """
        self.spectra.append(spectrum)

    def compute(self) -> tuple[float, float]:
        """Compute baseline statistics from collected spectra.

        Returns:
            Tuple of (mean, std).

        Raises:
            ValueError: If no spectra have been collected.
        """
        if not self.spectra:
            raise ValueError("No spectra collected for baseline")

        self.baseline_mean, self.baseline_std = compute_baseline(self.spectra)
        self.is_ready = True
        return self.baseline_mean, self.baseline_std

    def reset(self) -> None:
        """Reset baseline state for a new capture."""
        self.spectra = []
        self.baseline_mean = None
        self.baseline_std = None
        self.is_ready = False

    def sanity_check(self) -> bool:
        """Verify baseline statistics are reasonable.

        Returns:
            True if baseline_mean > 0 and baseline_std >= 0.
        """
        if not self.is_ready:
            return False
        if self.baseline_mean is None or self.baseline_std is None:
            return False
        return self.baseline_mean > 0 and self.baseline_std >= 0