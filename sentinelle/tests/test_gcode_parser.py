"""Tests du parseur G-code — gcode_parser.py.

Couvre (T-2.2) :
  1. Fichier avec G0 et G1 valides → segments corrects
  2. Fichier vide → liste vide
  3. Lignes ignorées (commentaires, autres commandes) → seuls G0/G1 produits

TODOS Phase 2 inclus :
  4. Segment zéro-longueur (G1 sans X ni Y) → filtré silencieusement

Toutes les fonctions testées sont des fonctions pures — zéro hardware.
"""

import pytest

from sentinelle.visual.gcode_parser import Point, Segment, parse_gcode


# ---------------------------------------------------------------------------
# Test 1 : G0 et G1 valides
# ---------------------------------------------------------------------------


def test_valid_g0_g1(tmp_path):
    """Fichier avec G0 et G1 → segments corrects avec types et coordonnées."""
    nc = tmp_path / "demo.nc"
    nc.write_text(
        "G0 X10 Y20\n"
        "G1 X50 Y80\n"
        "G0 X0 Y0\n",
        encoding="utf-8",
    )
    segments = parse_gcode(str(nc))

    assert len(segments) == 3

    # Segment 1 : G0 depuis (0,0) vers (10,20)
    assert segments[0].start == Point(0.0, 0.0)
    assert segments[0].end == Point(10.0, 20.0)
    assert segments[0].move_type == "rapid"

    # Segment 2 : G1 depuis (10,20) vers (50,80)
    assert segments[1].start == Point(10.0, 20.0)
    assert segments[1].end == Point(50.0, 80.0)
    assert segments[1].move_type == "feed"

    # Segment 3 : G0 retour à l'origine
    assert segments[2].start == Point(50.0, 80.0)
    assert segments[2].end == Point(0.0, 0.0)
    assert segments[2].move_type == "rapid"


# ---------------------------------------------------------------------------
# Test 2 : fichier vide
# ---------------------------------------------------------------------------


def test_empty_file(tmp_path):
    """Fichier vide → liste de segments vide."""
    nc = tmp_path / "empty.nc"
    nc.write_text("", encoding="utf-8")
    segments = parse_gcode(str(nc))
    assert segments == []


# ---------------------------------------------------------------------------
# Test 3 : lignes ignorées
# ---------------------------------------------------------------------------


def test_ignored_lines(tmp_path):
    """Commentaires et commandes non-G0/G1 sont ignorés."""
    nc = tmp_path / "mixed.nc"
    nc.write_text(
        "; programme de test\n"
        "(Tool change)\n"
        "T1 M06\n"
        "M03 S3000\n"
        "G0 X10 Y10\n"   # seul ce segment est produit
        "F500\n"
        "M05\n"
        "M30\n",
        encoding="utf-8",
    )
    segments = parse_gcode(str(nc))

    assert len(segments) == 1
    assert segments[0].move_type == "rapid"
    assert segments[0].end == Point(10.0, 10.0)


# ---------------------------------------------------------------------------
# Test 4 (TODOS) : segment zéro-longueur filtré
# ---------------------------------------------------------------------------


def test_zero_length_segment_filtered(tmp_path):
    """G1 sans X ni Y (feed rate seul) génère start==end → segment filtré.

    Référence : TODOS.md [TEST] Segment zéro-longueur.
    Le parseur filtre ces segments pour éviter ZeroDivisionError downstream.
    """
    nc = tmp_path / "feedrate.nc"
    nc.write_text(
        "G1 X50 Y50\n"  # segment réel : (0,0) → (50,50)
        "G1 F1000\n"    # feed rate uniquement — zéro déplacement → filtré
        "G1 X100 Y50\n" # segment réel : (50,50) → (100,50)
        ,
        encoding="utf-8",
    )
    segments = parse_gcode(str(nc))

    # Seuls 2 segments réels, la ligne F1000 est filtrée
    assert len(segments) == 2
    assert segments[0].end == Point(50.0, 50.0)
    assert segments[1].end == Point(100.0, 50.0)


# ---------------------------------------------------------------------------
# Tests additionnels — robustesse
# ---------------------------------------------------------------------------


def test_file_not_found_raises():
    """Fichier inexistant → FileNotFoundError."""
    with pytest.raises(FileNotFoundError):
        parse_gcode("/tmp/inexistant_sentinelle_test_xyz.nc")


def test_modal_coordinates(tmp_path):
    """Coordonnées modales : X absent sur une ligne conserve le X précédent."""
    nc = tmp_path / "modal.nc"
    nc.write_text(
        "G1 X30 Y10\n"  # (0,0) → (30,10)
        "G1 Y50\n"      # Y change, X reste 30 → (30,10) → (30,50)
        ,
        encoding="utf-8",
    )
    segments = parse_gcode(str(nc))
    assert len(segments) == 2
    assert segments[1].start == Point(30.0, 10.0)
    assert segments[1].end == Point(30.0, 50.0)
