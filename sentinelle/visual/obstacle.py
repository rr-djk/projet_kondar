"""Détection d'obstacles par masque HSV sur frame webcam.

Fonction pure : entrée (frame BGR) → sortie (BoundingBox | None).
Aucun état global, aucun effet de bord.

Note : Le fallback ArUco (T-1B.2b) est déféré — cette implémentation
se concentre sur la détection HSV uniquement.
"""

from __future__ import annotations

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


# Seuil minimal de surface (en pixels²) pour qu'un contour soit considéré
# comme un obstacle valide. Évite les faux positifs sur le bruit.
_MIN_CONTOUR_AREA = 500


def detect_obstacle(frame: np.ndarray) -> BoundingBox | None:
    """Détecte un obstacle orange dans une frame webcam via masque HSV.

    Convertit la frame BGR en HSV, applique un masque de couleur basé sur
    les constantes HSV_ORANGE_LOW/HIGH de config.py, puis extrait le plus
    grand contour valide.

    Args:
        frame: Image BGR brute de la webcam (numpy array H×W×3).

    Returns:
        BoundingBox du plus grand obstacle détecté, ou None si aucun
        contour ne dépasse le seuil minimal de surface.
    """
    # Convert BGR → HSV
    hsv = cv2.cvtColor(frame, cv2.COLOR_BGR2HSV)

    # Apply HSV mask for orange detection
    lower = np.array(config.HSV_ORANGE_LOW, dtype=np.uint8)
    upper = np.array(config.HSV_ORANGE_HIGH, dtype=np.uint8)
    mask = cv2.inRange(hsv, lower, upper)

    # Find contours in the masked image
    contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    if not contours:
        return None

    # Select the largest contour by area
    largest = max(contours, key=cv2.contourArea)
    area = cv2.contourArea(largest)

    if area < _MIN_CONTOUR_AREA:
        return None

    # Extract bounding box
    x, y, w, h = cv2.boundingRect(largest)
    return BoundingBox(x=x, y=y, w=w, h=h)
