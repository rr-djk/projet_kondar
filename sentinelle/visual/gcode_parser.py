"""Parseur G-code — extrait les trajectoires G0/G1 d'un fichier .nc.

Fonction pure : entrée (chemin fichier) → sortie (liste de segments).
Aucun état global, aucun effet de bord.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Point:
    """Point dans l'espace de travail en millimètres.

    Attributes:
        x: Coordonnée X en mm.
        y: Coordonnée Y en mm.
    """
    x: float
    y: float


@dataclass(frozen=True)
class Segment:
    """Segment de trajectoire entre deux points.

    Attributes:
        start: Point de départ du segment (mm).
        end: Point d'arrivée du segment (mm).
        move_type: Type de mouvement — "rapid" (G0) ou "feed" (G1).
    """
    start: Point
    end: Point
    move_type: str  # "rapid" | "feed"


# Regex pour extraire les commandes G0/G1 avec leurs coordonnées X/Y.
# Capture le numéro de commande (0 ou 1) et les valeurs X/Y optionnelles.
_GCODE_RE = re.compile(
    r"G\s*(?P<code>[01])"
    r"(?:\s+X\s*(?P<x>[+-]?\d*\.?\d+))?"
    r"(?:\s+Y\s*(?P<y>[+-]?\d*\.?\d+))?",
    re.IGNORECASE,
)


def parse_gcode(path: str) -> list[Segment]:
    """Parse un fichier G-code et extrait les segments G0/G1.

    Lit le fichier ligne par ligne, identifie les commandes G0 (mouvement
    rapide) et G1 (mouvement d'usinage), et construit une liste de segments
    avec les coordonnées en millimètres.

    Les coordonnées sont modales : si X ou Y est absent d'une ligne, la
    valeur précédente est conservée. La position initiale est (0, 0).

    Args:
        path: Chemin vers le fichier G-code (.nc).

    Returns:
        Liste de Segment ordonnée selon l'apparition dans le fichier.
        Liste vide si le fichier ne contient aucune commande G0/G1 valide.

    Raises:
        FileNotFoundError: Si le fichier n'existe pas.
    """
    segments: list[Segment] = []
    current_x = 0.0
    current_y = 0.0

    with open(path, "r", encoding="utf-8") as fh:
        for raw_line in fh:
            line = raw_line.strip()

            # Skip empty lines and comments
            if not line or line.startswith("(") or line.startswith(";"):
                continue

            match = _GCODE_RE.search(line)
            if not match:
                continue

            code = match.group("code")
            move_type = "rapid" if code == "0" else "feed"

            # Save current position as segment start
            start = Point(current_x, current_y)

            # Update coordinates (modal — keep previous if not specified)
            if match.group("x") is not None:
                current_x = float(match.group("x"))
            if match.group("y") is not None:
                current_y = float(match.group("y"))

            end = Point(current_x, current_y)

            segments.append(Segment(start=start, end=end, move_type=move_type))

    return segments
