"""Détection d'obstacles par masque HSV + fallback ArUco sur frame webcam.

Fonction pure : entrée (frame BGR) → sortie (BoundingBox | None).
Aucun état global, aucun effet de bord.

Stratégie :
1. Essayer détection HSV (orange) — rapide et fiable en bonnes conditions
2. Si échec, fallback ArUco avec throttle (évite 12fps si lumière mauvaise)
"""

from __future__ import annotations

import time
from dataclasses import dataclass

import cv2
import numpy as np

from sentinelle import config


@dataclass(frozen=True)
class BoundingBox:
    """Rectangle englobant un obstacle détecté dans une frame.

    Attributes:
        x: Coordonnée X du coin supérieur gauche (pixels).
        y: Coordonnée Y du coin supérieur gauche (pixels).
        w: Largeur du rectangle (pixels).
        h: Hauteur du rectangle (pixels).
    """
    x: int
    y: int
    w: int
    h: int


# MIN_CONTOUR_AREA déplacé dans config.py pour calibration centralisée


def _detect_obstacle_hsv(frame: np.ndarray) -> BoundingBox | None:
    """Détection HSV interne (orange)."""
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)
    lower = np.array(config.HSV_ORANGE_LOW, dtype=np.uint8)
    upper = np.array(config.HSV_ORANGE_HIGH, dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return None

    largest = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest)

    if area < config.MIN_CONTOUR_AREA:
        return None

    x, y, w, h = cv2.boundingRect(largest)
    return BoundingBox(x=x, y=y, w=w, h=h)


# Singleton ArUco — créé une seule fois à l'import (évite 60 allocations/s)
_aruco_dict = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_4X4_50)
_aruco_params = cv2.aruco.DetectorParameters()
_aruco_detector = cv2.aruco.ArucoDetector(_aruco_dict, _aruco_params)


def _detect_obstacle_aruco(frame: np.ndarray) -> BoundingBox | None:
    """Détection ArUco interne (fallback si HSV échoue).

    Utilise les marqueurs ArUco 4x4 pour la détection robuste en
    conditions de lumière variables.
    """
    corners, ids, _ = _aruco_detector.detectMarkers(frame)

    if ids is None or len(ids) == 0:
        return None

    # Prendre le premier marqueur détecté
    marker_corners = corners[0][0]
    x_min = int(marker_corners[:, 0].min())
    y_min = int(marker_corners[:, 1].min())
    x_max = int(marker_corners[:, 0].max())
    y_max = int(marker_corners[:, 1].max())

    return BoundingBox(x=x_min, y=y_min, w=x_max - x_min, h=y_max - y_min)


def detect_obstacle(frame: np.ndarray, allow_aruco: bool = True) -> BoundingBox | None:
    """Détecte un obstacle dans une frame webcam.

    Stratégie :
    1. Essayer détection HSV (orange) — rapide et précis
    2. Si échec et allow_aruco=True, tenter ArUco

    Args:
        frame: Image BGR brute de la webcam (numpy array H×W×3).
        allow_aruco: Si True, autorise le fallback ArUco. Le throttle
            est géré par l'appelant via ARUCO_THROTTLE_MS.

    Returns:
        BoundingBox du plus grand obstacle détecté, ou None si aucun
        obstacle n'est trouvé.
    """
    # Essayer HSV d'abord
    result = _detect_obstacle_hsv(frame)
    if result is not None:
        return result

    # Fallback ArUco si autorisé
    if allow_aruco:
        return _detect_obstacle_aruco(frame)

    return None
