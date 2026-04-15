"""Tests des fonctions pures d'analyse acoustique — analyzer.py.

Couvre (T-2.1) :
  1. Baseline normale → detect_anomaly retourne None
  2. Énergie à 2.0σ → "warn"
  3. Énergie à 3.0σ → "critical"
  4. Énergie à 1.9σ (en-dessous du seuil warn) → None
  5. Buffer partiel (spectre unique) : std=0, détection toujours fonctionnelle

Toutes les fonctions testées sont des fonctions pures — zéro hardware.
"""

import numpy as np
import pytest

from sentinelle.acoustic.analyzer import (
    compute_baseline,
    compute_fft,
    detect_anomaly,
    detect_anomaly_from_energy,
)


# ---------------------------------------------------------------------------
# Fixtures de baseline réutilisables
# ---------------------------------------------------------------------------


def _make_baseline(mean: float = 10.0, std: float = 2.0):
    """Construit une baseline synthétique avec (mean, std) données.

    Deux spectres à energies symétriques autour de mean produisent
    mean exact et std exact : [mean-std, mean+std].
    """
    spectra = [
        np.array([mean - std]),
        np.array([mean + std]),
    ]
    baseline_mean, baseline_std = compute_baseline(spectra)
    return baseline_mean, baseline_std


# ---------------------------------------------------------------------------
# Test 1 : baseline normale → None
# ---------------------------------------------------------------------------


def test_no_anomaly_below_warn():
    """Énergie égale à la moyenne de baseline → aucune anomalie détectée."""
    mean, std = _make_baseline(mean=10.0, std=2.0)
    # energy = mean → en-dessous du seuil warn (mean + 2*std = 14.0)
    spectrum = np.array([mean])
    result = detect_anomaly(spectrum, mean, std)
    assert result is None


# ---------------------------------------------------------------------------
# Test 2 : exactement à 2.0σ → "warn"
# ---------------------------------------------------------------------------


def test_detect_warn_at_2_sigma():
    """Énergie exactement à baseline + 2.0σ → niveau 'warn'."""
    mean, std = _make_baseline(mean=10.0, std=2.0)
    # threshold_warn = 10 + 2*2 = 14.0
    threshold_warn = mean + 2.0 * std
    spectrum = np.array([threshold_warn])
    result = detect_anomaly(spectrum, mean, std)
    assert result == "warn"


# ---------------------------------------------------------------------------
# Test 3 : exactement à 3.0σ → "critical"
# ---------------------------------------------------------------------------


def test_detect_critical_at_3_sigma():
    """Énergie exactement à baseline + 3.0σ → niveau 'critical'."""
    mean, std = _make_baseline(mean=10.0, std=2.0)
    # threshold_critical = 10 + 3*2 = 16.0
    threshold_critical = mean + 3.0 * std
    spectrum = np.array([threshold_critical])
    result = detect_anomaly(spectrum, mean, std)
    assert result == "critical"


# ---------------------------------------------------------------------------
# Test 4 : 1.9σ (en-dessous du seuil warn) → None
# ---------------------------------------------------------------------------


def test_below_warn_boundary_1_9_sigma():
    """Énergie à 1.9σ (juste sous le seuil warn 2.0σ) → None."""
    mean, std = _make_baseline(mean=10.0, std=2.0)
    # energy = 10 + 1.9*2 = 13.8 < threshold_warn 14.0
    energy_below_warn = mean + 1.9 * std
    spectrum = np.array([energy_below_warn])
    result = detect_anomaly(spectrum, mean, std)
    assert result is None


# ---------------------------------------------------------------------------
# Test 5 : buffer partiel (spectre unique, std=0)
# ---------------------------------------------------------------------------


def test_partial_buffer_single_spectrum():
    """compute_baseline avec un seul spectre : std=0, détection reste fonctionnelle."""
    single_spectrum = np.array([5.0, 3.0, 2.0])  # sum = 10.0
    mean, std = compute_baseline([single_spectrum])

    # Avec un seul spectre : std est forcément 0
    assert std == 0.0
    assert mean == pytest.approx(10.0)

    # Avec std=0, tout seuil = mean. energy >= mean → "critical" (vérifié en premier)
    above_mean = np.array([10.5])
    assert detect_anomaly(above_mean, mean, std) == "critical"

    # energy < mean → None
    below_mean = np.array([9.9])
    assert detect_anomaly(below_mean, mean, std) is None


# ---------------------------------------------------------------------------
# Tests additionnels — compute_fft et detect_anomaly_from_energy
# ---------------------------------------------------------------------------


def test_compute_fft_returns_positive_magnitudes():
    """compute_fft retourne un spectre de magnitudes positives."""
    audio = np.sin(2 * np.pi * 440 * np.arange(512) / 44100).astype(np.float32)
    spectrum = compute_fft(audio)
    assert spectrum.shape[0] == 257  # rfft(512) → 257 bins
    assert np.all(spectrum >= 0)


def test_compute_baseline_empty_raises():
    """compute_baseline avec liste vide lève ValueError."""
    with pytest.raises(ValueError, match="empty"):
        compute_baseline([])


def test_detect_anomaly_from_energy_matches_detect_anomaly():
    """detect_anomaly_from_energy et detect_anomaly produisent le même résultat."""
    mean, std = _make_baseline(mean=10.0, std=2.0)
    energy = mean + 2.5 * std  # entre warn et critical
    spectrum = np.array([energy])

    via_spectrum = detect_anomaly(spectrum, mean, std)
    via_energy = detect_anomaly_from_energy(energy, mean, std)

    assert via_spectrum == via_energy == "warn"
