"""Path planning A* sur grille 50×50 pour évitement d'obstacles.

Fonction pure : entrée (positions mm + obstacles) → sortie (chemin grille | None).
Aucun état global, aucun effet de bord.

Timeout 150ms garanti — retourne None si le calcul dépasse cette limite.
"""

from __future__ import annotations

import heapq
import time
from dataclasses import dataclass, field

from sentinelle import config
from sentinelle.visual.obstacle import BoundingBox


@dataclass(frozen=True)
class GridPoint:
    """Cellule sur la grille de path planning.

    Attributes:
        x: Colonne sur la grille (0 à GRID_SIZE[0]-1).
        y: Ligne sur la grille (0 à GRID_SIZE[1]-1).
    """
    x: int
    y: int


# Timeout maximal pour le calcul A* en secondes
_PLANNER_TIMEOUT_S = 0.150  # 150ms


def _mm_to_grid(x_mm: float, y_mm: float) -> GridPoint:
    """Convertit des coordonnées mm en coordonnées grille.

    Args:
        x_mm: Coordonnée X en millimètres.
        y_mm: Coordonnée Y en millimètres.

    Returns:
        GridPoint avec coordonnées clampées dans les limites de la grille.
    """
    cols, rows = config.GRID_SIZE
    wx, wy = config.WORKSPACE_MM

    gx = int(x_mm / wx * cols)
    gy = int(y_mm / wy * rows)

    # Clamp to grid boundaries
    gx = max(0, min(gx, cols - 1))
    gy = max(0, min(gy, rows - 1))

    return GridPoint(x=gx, y=gy)


def _build_obstacle_set(obstacles: list[BoundingBox]) -> set[tuple[int, int]]:
    """Marque les cellules grille occupées par les obstacles.

    Convertit chaque BoundingBox (pixels) en coordonnées grille et
    marque toutes les cellules couvertes comme bloquées.

    Args:
        obstacles: Liste de BoundingBox détectées par detect_obstacle().

    Returns:
        Ensemble de tuples (gx, gy) représentant les cellules bloquées.
    """
    blocked: set[tuple[int, int]] = set()
    cols, rows = config.GRID_SIZE
    wx, wy = config.WORKSPACE_MM
    cw, ch = config.WEBCAM_MAX_RES

    for obs in obstacles:
        # Convert pixel bounding box to grid coordinates
        x1 = int(obs.x / cw * cols)
        y1 = int(obs.y / ch * rows)
        x2 = int((obs.x + obs.w) / cw * cols)
        y2 = int((obs.y + obs.h) / ch * rows)

        # Clamp to grid boundaries
        x1 = max(0, min(x1, cols - 1))
        y1 = max(0, min(y1, rows - 1))
        x2 = max(0, min(x2, cols - 1))
        y2 = max(0, min(y2, rows - 1))

        # Mark all cells within the bounding box as blocked
        for gx in range(x1, x2 + 1):
            for gy in range(y1, y2 + 1):
                blocked.add((gx, gy))

    return blocked


def find_path(
    start_mm: tuple[float, float],
    goal_mm: tuple[float, float],
    obstacles: list[BoundingBox],
) -> list[GridPoint] | None:
    """Calcule un chemin A* de start à goal en évitant les obstacles.

    Algorithme A* avec heuristique de Manhattan sur grille 4-connectée.
    Le calcul est limité à 150ms — au-delà, retourne None.

    Args:
        start_mm: Position de départ (x_mm, y_mm).
        goal_mm: Position d'arrivée (x_mm, y_mm).
        obstacles: Liste de BoundingBox à éviter.

    Returns:
        Liste de GridPoints du chemin calculé (incluant start et goal),
        ou None si aucun chemin n'existe ou si le timeout est atteint.
    """
    start = _mm_to_grid(start_mm[0], start_mm[1])
    goal = _mm_to_grid(goal_mm[0], goal_mm[1])
    blocked = _build_obstacle_set(obstacles)

    # If start or goal is blocked, no path possible
    if (start.x, start.y) in blocked or (goal.x, goal.y) in blocked:
        return None

    deadline = time.monotonic() + _PLANNER_TIMEOUT_S
    _, rows = config.GRID_SIZE

    # A* implementation
    # Priority queue: (f_score, counter, grid_point)
    # counter breaks ties and avoids comparing GridPoint
    counter = 0
    open_set: list[tuple[float, int, GridPoint]] = [(0, counter, start)]
    came_from: dict[tuple[int, int], tuple[int, int]] = {}
    g_score: dict[tuple[int, int], float] = {(start.x, start.y): 0}

    # 4-connectivity: up, down, left, right
    directions = [(0, -1), (0, 1), (-1, 0), (1, 0)]

    while open_set:
        # Check timeout
        if time.monotonic() > deadline:
            return None

        _, _, current = heapq.heappop(open_set)
        current_key = (current.x, current.y)

        # Goal reached
        if current == goal:
            # Reconstruct path
            path = [current]
            while current_key in came_from:
                current_key = came_from[current_key]
                path.append(GridPoint(x=current_key[0], y=current_key[1]))
            path.reverse()
            return path

        # Explore neighbors
        for dx, dy in directions:
            nx, ny = current.x + dx, current.y + dy
            neighbor_key = (nx, ny)

            # Check bounds
            if nx < 0 or nx >= config.GRID_SIZE[0] or ny < 0 or ny >= rows:
                continue

            # Check if blocked
            if neighbor_key in blocked:
                continue

            tentative_g = g_score[current_key] + 1

            if tentative_g < g_score.get(neighbor_key, float("inf")):
                came_from[neighbor_key] = current_key
                g_score[neighbor_key] = tentative_g
                # Manhattan distance heuristic
                h = abs(nx - goal.x) + abs(ny - goal.y)
                f = tentative_g + h
                counter += 1
                heapq.heappush(
                    open_set, (f, counter, GridPoint(x=nx, y=ny))
                )

    # No path found
    return None
