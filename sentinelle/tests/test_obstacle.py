"""Tests de détection d'obstacles par masque HSV — obstacle.py.

Couvre (T-2.4) :
  1. Frame synthétique orange → BoundingBox non-None
  2. Frame synthétique grise → None

Les frames sont des tableaux NumPy synthétiques — zéro webcam, zéro hardware.
"""

import cv2
import numpy as np

from sentinelle.visual.obstacle import BoundingBox, detect_obstacle


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_orange_frame(width: int = 640, height: int = 480) -> np.ndarray:
    """Crée une frame BGR avec un carré orange centré suffisamment grand (> 500 px²).

    Couleur : HSV (15, 200, 200) — dans la plage HSV_ORANGE_LOW/HIGH (5-25, 100+, 100+).
    Converti en BGR pour simuler l'entrée réelle de la webcam.
    """
    # Construire en HSV puis convertir en BGR
    hsv_frame = np.zeros((height, width, 3), dtype=np.uint8)
    # Carré de 100×100 centré — aire = 10 000 px² >> seuil minimal 500
    cy, cx = height // 2, width // 2
    half = 50
    hsv_frame[cy - half : cy + half, cx - half : cx + half] = [15, 200, 200]
    return cv2.cvtColor(hsv_frame, cv2.COLOR_HSV2BGR)


def _make_gray_frame(width: int = 640, height: int = 480) -> np.ndarray:
    """Crée une frame BGR uniforme grise — aucun orange."""
    return np.full((height, width, 3), 128, dtype=np.uint8)


# ---------------------------------------------------------------------------
# Test 1 : frame orange → BoundingBox
# ---------------------------------------------------------------------------


def test_orange_frame_returns_bounding_box():
    """Une frame avec un carré orange détecte un obstacle et retourne une BoundingBox."""
    frame = _make_orange_frame()
    result = detect_obstacle(frame)

    assert result is not None
    assert isinstance(result, BoundingBox)
    # La BoundingBox doit avoir des dimensions cohérentes
    assert result.w > 0
    assert result.h > 0


# ---------------------------------------------------------------------------
# Test 2 : frame grise → None
# ---------------------------------------------------------------------------


def test_gray_frame_returns_none():
    """Une frame sans orange retourne None."""
    frame = _make_gray_frame()
    result = detect_obstacle(frame)
    assert result is None


# ---------------------------------------------------------------------------
# Tests additionnels — robustesse
# ---------------------------------------------------------------------------


def test_bounding_box_within_frame_bounds():
    """La BoundingBox reste dans les dimensions de la frame."""
    frame = _make_orange_frame(width=640, height=480)
    bbox = detect_obstacle(frame)

    assert bbox is not None
    assert bbox.x >= 0
    assert bbox.y >= 0
    assert bbox.x + bbox.w <= 640
    assert bbox.y + bbox.h <= 480


def test_tiny_orange_speck_below_threshold():
    """Un tout petit pixel orange (< seuil minimal 500 px²) est ignoré."""
    frame = _make_gray_frame()
    # Un carré 10×10 = 100 px² — sous le seuil minimal
    cy, cx = 240, 320
    half = 5
    hsv_small = np.zeros((480, 640, 3), dtype=np.uint8)
    hsv_small[cy - half : cy + half, cx - half : cx + half] = [15, 200, 200]
    small_frame = cv2.cvtColor(hsv_small, cv2.COLOR_HSV2BGR)

    result = detect_obstacle(small_frame)
    assert result is None
