"""Fonctions pures pour l'analyse acoustique.

Contient les fonctions de traitement FFT et détection d'anomalie
sans état mutable — toutes sont des fonctions pures.
"""

from __future__ import annotations

import numpy as np

from sentinelle import config


def compute_fft(audio_block: np.ndarray) -> np.ndarray:
    """Compute FFT magnitude spectrum for an audio block.

    Args:
        audio_block: 1D numpy array of audio samples.

    Returns:
        Magnitude spectrum (half FFT size).
    """
    fft = np.fft.rfft(audio_block)
    return np.abs(fft)


def compute_band_energy(spectrum: np.ndarray, band_hz: tuple[int, int]) -> float:
    """Compute energy in a frequency band.

    Args:
        spectrum: Magnitude spectrum from compute_fft.
        band_hz: (low_hz, high_hz) frequency band.

    Returns:
        Sum of magnitude squared in the band.
    """
    low_hz, high_hz = band_hz
    n_bins = len(spectrum)
    bin_resolution = config.AUDIO_SR / (2 * n_bins)

    low_bin = int(low_hz / bin_resolution)
    high_bin = int(high_hz / bin_resolution)

    low_bin = max(0, low_bin)
    high_bin = min(n_bins - 1, high_bin)

    band = spectrum[low_bin : high_bin + 1]
    return float(np.sum(band**2))


def compute_baseline(
    spectra: list[np.ndarray],
) -> tuple[float, float]:
    """Compute baseline statistics from a list of spectra.

    Args:
        spectra: List of magnitude spectra collected during baseline.

    Returns:
        Tuple of (mean, std) of the summed energy.

    Raises:
        ValueError: If spectra is empty.
    """
    if not spectra:
        raise ValueError("Cannot compute baseline from empty spectra list")

    energies = [np.sum(s) for s in spectra]
    return float(np.mean(energies)), float(np.std(energies))


def detect_anomaly(
    spectrum: np.ndarray,
    baseline_mean: float,
    baseline_std: float,
    warn_sigma: float = config.ANOMALY_WARN_SIGMA,
    critical_sigma: float = config.ANOMALY_CRITICAL_SIGMA,
) -> str | None:
    """Detect anomaly by comparing spectrum to baseline.

    Args:
        spectrum: Current magnitude spectrum.
        baseline_mean: Baseline mean from compute_baseline.
        baseline_std: Baseline standard deviation.
        warn_sigma: Number of sigma for warn level (default from config).
        critical_sigma: Number of sigma for critical level (default from config).

    Returns:
        "warn" if amplitude >= baseline + warn_sigma * std,
        "critical" if amplitude >= baseline + critical_sigma * std,
        None otherwise.
    """
    energy = np.sum(spectrum)

    threshold_critical = baseline_mean + critical_sigma * baseline_std
    threshold_warn = baseline_mean + warn_sigma * baseline_std

    if energy >= threshold_critical:
        return "critical"
    elif energy >= threshold_warn:
        return "warn"
    return None


def detect_anomaly_from_energy(
    energy: float,
    baseline_mean: float,
    baseline_std: float,
    warn_sigma: float = config.ANOMALY_WARN_SIGMA,
    critical_sigma: float = config.ANOMALY_CRITICAL_SIGMA,
) -> str | None:
    """Detect anomaly from pre-computed energy value.

    Args:
        energy: Pre-computed energy value (sum of spectrum).
        baseline_mean: Baseline mean from compute_baseline.
        baseline_std: Baseline standard deviation.
        warn_sigma: Number of sigma for warn level.
        critical_sigma: Number of sigma for critical level.

    Returns:
        "warn", "critical", or None.
    """
    threshold_critical = baseline_mean + critical_sigma * baseline_std
    threshold_warn = baseline_mean + warn_sigma * baseline_std

    if energy >= threshold_critical:
        return "critical"
    elif energy >= threshold_warn:
        return "warn"
    return None