"""Contrat IPC partagé entre Pi et Laptop.

Définit le schéma des messages WebSocket et les fonctions
de sérialisation/désérialisation avec validation stricte.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Literal


class InvalidProtocolMessage(ValueError):
    """Raised when a JSON message doesn't match the expected schema."""
    pass


@dataclass
class AcousticEvent:
    """Événement acoustique envoyé par le Pi au laptop.

    Attributes:
        type: Toujours "acoustic".
        severity: "warn" (alerte jaune) ou "critical" (alerte rouge + pause).
        ts: Timestamp epoch en millisecondes.
    """
    type: Literal["acoustic"]
    severity: Literal["warn", "critical"]
    ts: int


_VALID_TYPES = {"acoustic"}
_VALID_SEVERITIES = {"warn", "critical"}


def to_json(event: AcousticEvent) -> str:
    """Serialize an AcousticEvent to a JSON string.

    Args:
        event: The event to serialize.

    Returns:
        JSON string with keys: type, severity, ts.
    """
    return json.dumps({
        "type": event.type,
        "severity": event.severity,
        "ts": event.ts,
    })


def from_json(data: str) -> AcousticEvent:
    """Deserialize a JSON string into an AcousticEvent with strict validation.

    Args:
        data: JSON string to parse.

    Returns:
        Validated AcousticEvent instance.

    Raises:
        InvalidProtocolMessage: If JSON is malformed or fields are invalid.
    """
    try:
        obj = json.loads(data)
    except (json.JSONDecodeError, TypeError) as exc:
        raise InvalidProtocolMessage(f"Invalid JSON: {exc}") from exc

    if not isinstance(obj, dict):
        raise InvalidProtocolMessage("Message must be a JSON object")

    # Validate required fields
    for field in ("type", "severity", "ts"):
        if field not in obj:
            raise InvalidProtocolMessage(f"Missing required field: {field}")

    # Validate type
    if obj["type"] not in _VALID_TYPES:
        raise InvalidProtocolMessage(
            f"Invalid type: {obj['type']!r}. Must be one of {_VALID_TYPES}"
        )

    # Validate severity
    if obj["severity"] not in _VALID_SEVERITIES:
        raise InvalidProtocolMessage(
            f"Invalid severity: {obj['severity']!r}. Must be one of {_VALID_SEVERITIES}"
        )

    # Validate ts is an integer
    if not isinstance(obj["ts"], int):
        raise InvalidProtocolMessage(
            f"Invalid ts: {obj['ts']!r}. Must be an integer"
        )

    return AcousticEvent(
        type=obj["type"],
        severity=obj["severity"],
        ts=obj["ts"],
    )
