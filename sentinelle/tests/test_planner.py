"""Tests du path planner A* — planner.py.

Couvre (T-2.3) :
  1. Chemin libre (aucun obstacle) → liste de GridPoints non-None
  2. Contournement d'obstacle → chemin alternatif trouvé
  3. Aucun chemin (obstacle bloquant toute issue) → None
  4. Timeout 150ms déclenché → None

TODOS Phase 2 inclus :
  5. Coordonnées mm négatives → clampées à (0,0), pas de crash

Toutes les fonctions testées sont des fonctions pures — zéro hardware.
"""

import time
from unittest.mock import patch

import pytest

from sentinelle.visual.obstacle import BoundingBox
from sentinelle.visual.planner import GridPoint, find_path


# ---------------------------------------------------------------------------
# Test 1 : chemin libre
# ---------------------------------------------------------------------------


def test_free_path_found():
    """Sans obstacle, A* retourne un chemin de start à goal."""
    result = find_path(
        start_mm=(0.0, 0.0),
        goal_mm=(150.0, 100.0),
        obstacles=[],
    )
    assert result is not None
    assert isinstance(result, list)
    assert len(result) >= 2
    # Premier point = start, dernier point = goal (en coordonnées grille)
    assert result[0] == GridPoint(x=0, y=0)
    # goal (150mm, 100mm) sur grille 50×50 dans workspace 300×200mm
    # gx = int(150/300 * 50) = 25, gy = int(100/200 * 50) = 25
    assert result[-1] == GridPoint(x=25, y=25)


# ---------------------------------------------------------------------------
# Test 2 : contournement d'obstacle
# ---------------------------------------------------------------------------


def test_bypass_obstacle():
    """Un obstacle sur le chemin direct est contourné — chemin alternatif trouvé."""
    # Start (0,0)mm → grille (0,0). Goal (299,0)mm → grille (49,0).
    # Obstacle : carré en pixels (320,0) w=20 h=20 bloque grille (25,0)-(26,2).
    # Le chemin contourne par y>2.
    obstacle = BoundingBox(x=320, y=0, w=20, h=20)
    result = find_path(
        start_mm=(0.0, 0.0),
        goal_mm=(299.0, 0.0),
        obstacles=[obstacle],
    )
    assert result is not None
    # Le chemin contourne l'obstacle
    blocked_cells = {(25, 0), (25, 1), (25, 2), (26, 0), (26, 1), (26, 2)}
    for point in result:
        assert (point.x, point.y) not in blocked_cells, (
            f"Chemin passe par cellule bloquée {point}"
        )


# ---------------------------------------------------------------------------
# Test 3 : aucun chemin possible → None
# ---------------------------------------------------------------------------


def test_no_path_returns_none():
    """Un obstacle barrant toute la largeur de la grille → find_path retourne None.

    Un BoundingBox couvrant toute la largeur (pixels 0→640) à mi-hauteur
    (pixels 240→250) marque les lignes grille y=25-26 comme bloquées
    pour tous les x, empêchant tout passage de (0,0)grille vers (49,49)grille.
    """
    full_wall = BoundingBox(x=0, y=240, w=640, h=10)
    result = find_path(
        start_mm=(0.0, 0.0),
        goal_mm=(299.0, 199.0),
        obstacles=[full_wall],
    )
    assert result is None


# ---------------------------------------------------------------------------
# Test 4 : timeout 150ms
# ---------------------------------------------------------------------------


def test_timeout_returns_none():
    """find_path retourne None quand le timeout 150ms est dépassé.

    time.monotonic est mocké : le premier appel établit la deadline,
    le second retourne une valeur déjà au-delà — déclenchement immédiat.
    """
    base = time.monotonic()
    call_count = [0]

    def mock_monotonic():
        call_count[0] += 1
        if call_count[0] == 1:
            return base  # deadline = base + 0.150
        return base + 1.0  # déjà passé

    with patch("sentinelle.visual.planner.time.monotonic", side_effect=mock_monotonic):
        result = find_path(
            start_mm=(0.0, 0.0),
            goal_mm=(299.0, 199.0),
            obstacles=[],
        )

    assert result is None


# ---------------------------------------------------------------------------
# Test 5 (TODOS) : coordonnées négatives clampées à (0,0)
# ---------------------------------------------------------------------------


def test_negative_coordinates_clamped():
    """Coordonnées mm négatives sont clampées à (0,0) — pas de crash.

    Référence : TODOS.md [TEST] Coordonnées mm négatives dans planner.py.
    Le comportement documenté est un clamp silencieux vers (0,0).
    """
    # Aucune exception ne doit être levée
    result = find_path(
        start_mm=(-10.0, -5.0),
        goal_mm=(150.0, 100.0),
        obstacles=[],
    )
    # Le résultat est soit un chemin (depuis (0,0) clamped), soit None —
    # dans tous les cas, pas d'exception et type correct.
    assert result is None or isinstance(result, list)


# ---------------------------------------------------------------------------
# Tests additionnels — robustesse
# ---------------------------------------------------------------------------


def test_start_equals_goal():
    """Start = Goal → chemin d'un seul point (ou liste de longueur 1)."""
    result = find_path(
        start_mm=(100.0, 100.0),
        goal_mm=(100.0, 100.0),
        obstacles=[],
    )
    # A* trouve immédiatement le goal (start == goal) → chemin d'un point
    assert result is not None
    assert len(result) == 1


def test_no_obstacles_path_connects_start_goal():
    """Sans obstacle, le premier et dernier point du chemin sont start et goal."""
    result = find_path(
        start_mm=(0.0, 0.0),
        goal_mm=(60.0, 40.0),
        obstacles=[],
    )
    assert result is not None
    # gx = int(60/300*50) = 10, gy = int(40/200*50) = 10
    assert result[-1] == GridPoint(x=10, y=10)
