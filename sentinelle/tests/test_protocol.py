"""Tests du contrat IPC — protocol.py.

Couvre :
  - Round-trip JSON warn  (T-2.5 cas 1)
  - Round-trip JSON critical  (T-2.5 cas 2)
  - Champ manquant → InvalidProtocolMessage  (T-2.5 cas 3)
  - Cas additionnels : type invalide, severity invalide, ts string, ts négatif, JSON malformé
"""

import json

import pytest

from sentinelle.protocol import (
    AcousticEvent,
    InvalidProtocolMessage,
    from_json,
    to_json,
)


# ---------------------------------------------------------------------------
# Round-trip JSON
# ---------------------------------------------------------------------------


def test_round_trip_warn():
    """Sérialiser un événement warn puis le désérialiser produit un objet identique."""
    event = AcousticEvent(type="acoustic", severity="warn", ts=1_713_000_000_000)
    result = from_json(to_json(event))
    assert result.type == "acoustic"
    assert result.severity == "warn"
    assert result.ts == 1_713_000_000_000


def test_round_trip_critical():
    """Sérialiser un événement critical puis le désérialiser produit un objet identique."""
    event = AcousticEvent(type="acoustic", severity="critical", ts=1_713_000_000_001)
    result = from_json(to_json(event))
    assert result.type == "acoustic"
    assert result.severity == "critical"
    assert result.ts == 1_713_000_000_001


# ---------------------------------------------------------------------------
# Validation — champ manquant
# ---------------------------------------------------------------------------


def test_missing_severity_raises():
    """Un message sans 'severity' lève InvalidProtocolMessage."""
    with pytest.raises(InvalidProtocolMessage, match="severity"):
        from_json('{"type": "acoustic", "ts": 1713000000000}')


def test_missing_type_raises():
    """Un message sans 'type' lève InvalidProtocolMessage."""
    with pytest.raises(InvalidProtocolMessage, match="type"):
        from_json('{"severity": "warn", "ts": 1713000000000}')


def test_missing_ts_raises():
    """Un message sans 'ts' lève InvalidProtocolMessage."""
    with pytest.raises(InvalidProtocolMessage, match="ts"):
        from_json('{"type": "acoustic", "severity": "warn"}')


# ---------------------------------------------------------------------------
# Validation — valeurs incorrectes
# ---------------------------------------------------------------------------


def test_invalid_type_raises():
    """Un 'type' non reconnu lève InvalidProtocolMessage."""
    with pytest.raises(InvalidProtocolMessage):
        from_json('{"type": "vision", "severity": "warn", "ts": 1713000000000}')


def test_invalid_severity_raises():
    """Une 'severity' non reconnue lève InvalidProtocolMessage."""
    with pytest.raises(InvalidProtocolMessage):
        from_json('{"type": "acoustic", "severity": "info", "ts": 1713000000000}')


def test_ts_string_raises():
    """Un 'ts' de type string lève InvalidProtocolMessage."""
    with pytest.raises(InvalidProtocolMessage):
        from_json('{"type": "acoustic", "severity": "warn", "ts": "1713000000000"}')


def test_ts_negative_raises():
    """Un 'ts' négatif lève InvalidProtocolMessage."""
    with pytest.raises(InvalidProtocolMessage):
        from_json('{"type": "acoustic", "severity": "warn", "ts": -1}')


def test_malformed_json_raises():
    """Du JSON invalide lève InvalidProtocolMessage."""
    with pytest.raises(InvalidProtocolMessage):
        from_json("{invalid json}")
