"""Finite State Machine pour SENTINELLE CNC.

Gère les 8 états du système et les transitions entre eux.
Deux flags indépendants (acoustic_alert, path_blocked) permettent
de tracker les deux sources d'alerte séparément.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class State(Enum):
    """États possibles du système."""

    IDLE = "idle"
    BASELINE_CAPTURING = "baseline_capturing"
    RUNNING_NORMAL = "running_normal"
    ALERT_WARN = "alert_warn"
    ALERT_CRITICAL = "alert_critical"
    PAUSED_PATH_BLOCKED = "paused_path_blocked"
    PAUSED_ACOUSTIC = "paused_acoustic"
    CONFIRMING = "confirming"


class Event(Enum):
    """Événements qui déclenchent des transitions."""

    START = "start"
    BASELINE_DONE = "baseline_done"
    ACOUSTIC_WARN = "acoustic_warn"
    ACOUSTIC_CRITICAL = "acoustic_critical"
    DISMISS = "dismiss"
    PATH_FOUND = "path_found"
    PATH_BLOCKED = "path_blocked"
    CONFIRMER = "confirmer"
    RESUME = "resume"


class InvalidTransition(Exception):
    """Raised when a transition is not allowed from the current state."""

    pass


# Table de transitions valides: (from_state, event) -> to_state
_TRANSITIONS: dict[tuple[State, Event], State] = {
    (State.IDLE, Event.START): State.BASELINE_CAPTURING,
    (State.BASELINE_CAPTURING, Event.BASELINE_DONE): State.RUNNING_NORMAL,
    (State.RUNNING_NORMAL, Event.ACOUSTIC_WARN): State.ALERT_WARN,
    (State.RUNNING_NORMAL, Event.ACOUSTIC_CRITICAL): State.ALERT_CRITICAL,
    (State.RUNNING_NORMAL, Event.PATH_BLOCKED): State.PAUSED_PATH_BLOCKED,
    (State.ALERT_WARN, Event.ACOUSTIC_CRITICAL): State.ALERT_CRITICAL,
    (State.ALERT_WARN, Event.DISMISS): State.RUNNING_NORMAL,
    (State.ALERT_WARN, Event.PATH_BLOCKED): State.PAUSED_PATH_BLOCKED,
    (State.ALERT_CRITICAL, Event.DISMISS): State.RUNNING_NORMAL,
    (State.PAUSED_PATH_BLOCKED, Event.PATH_FOUND): State.RUNNING_NORMAL,
    (State.PAUSED_PATH_BLOCKED, Event.CONFIRMER): State.CONFIRMING,
    (State.PAUSED_PATH_BLOCKED, Event.ACOUSTIC_CRITICAL): State.PAUSED_ACOUSTIC,
    (State.PAUSED_ACOUSTIC, Event.DISMISS): State.RUNNING_NORMAL,
    (State.CONFIRMING, Event.RESUME): State.RUNNING_NORMAL,
    (State.CONFIRMING, Event.CONFIRMER): State.CONFIRMING,  # idempotent
}


@dataclass
class AppState:
    """État courant du système SENTINELLE CNC.

    Attributes:
        state: État courant de la FSM.
        acoustic_alert: True si une alerte acoustique est active.
        path_blocked: True si le path planner n'a trouvé aucun chemin.
    """

    state: State = State.IDLE
    acoustic_alert: bool = False
    path_blocked: bool = False

    def transition(self, event: Event) -> None:
        """Apply a state transition.

        Args:
            event: The event triggering the transition.

        Raises:
            InvalidTransition: If the transition is not allowed.
        """
        key = (self.state, event)
        if key not in _TRANSITIONS:
            raise InvalidTransition(
                f"Invalid transition: {event.value} from {self.state.value}"
            )
        self.state = _TRANSITIONS[key]

        # Update flags based on transitions
        if event in (Event.ACOUSTIC_WARN, Event.ACOUSTIC_CRITICAL):
            self.acoustic_alert = True
        elif event == Event.DISMISS:
            self.acoustic_alert = False

        if event == Event.PATH_BLOCKED:
            self.path_blocked = True
        elif event in (Event.PATH_FOUND, Event.RESUME):
            self.path_blocked = False
