"""Tests de la FSM AppState — state.py.

Couvre (T-2.6) :
  - 7 transitions légales
  - 3 transitions illégales → InvalidTransition

Flags indépendants :
  - acoustic_alert : True après ACOUSTIC_WARN / ACOUSTIC_CRITICAL, False après DISMISS
  - path_blocked : True après PATH_BLOCKED, False après PATH_FOUND / RESUME / DISMISS
"""

import pytest

from sentinelle.state import AppState, Event, InvalidTransition, State


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make(state: State) -> AppState:
    """Crée un AppState en forçant l'état interne directement."""
    app = AppState()
    app.state = state
    return app


# ---------------------------------------------------------------------------
# Transitions légales (7)
# ---------------------------------------------------------------------------


def test_idle_start_baseline_capturing():
    """IDLE + START → BASELINE_CAPTURING."""
    app = AppState()
    app.transition(Event.START)
    assert app.state == State.BASELINE_CAPTURING


def test_baseline_done_running_normal():
    """BASELINE_CAPTURING + BASELINE_DONE → RUNNING_NORMAL."""
    app = _make(State.BASELINE_CAPTURING)
    app.transition(Event.BASELINE_DONE)
    assert app.state == State.RUNNING_NORMAL


def test_running_normal_acoustic_warn_sets_flag():
    """RUNNING_NORMAL + ACOUSTIC_WARN → ALERT_WARN et acoustic_alert=True."""
    app = _make(State.RUNNING_NORMAL)
    app.transition(Event.ACOUSTIC_WARN)
    assert app.state == State.ALERT_WARN
    assert app.acoustic_alert is True


def test_running_normal_acoustic_critical():
    """RUNNING_NORMAL + ACOUSTIC_CRITICAL → ALERT_CRITICAL et acoustic_alert=True."""
    app = _make(State.RUNNING_NORMAL)
    app.transition(Event.ACOUSTIC_CRITICAL)
    assert app.state == State.ALERT_CRITICAL
    assert app.acoustic_alert is True


def test_running_normal_path_blocked_sets_flag():
    """RUNNING_NORMAL + PATH_BLOCKED → PAUSED_PATH_BLOCKED et path_blocked=True."""
    app = _make(State.RUNNING_NORMAL)
    app.transition(Event.PATH_BLOCKED)
    assert app.state == State.PAUSED_PATH_BLOCKED
    assert app.path_blocked is True


def test_alert_warn_dismiss_clears_flag():
    """ALERT_WARN + DISMISS → RUNNING_NORMAL et acoustic_alert=False."""
    app = _make(State.ALERT_WARN)
    app.acoustic_alert = True
    app.transition(Event.DISMISS)
    assert app.state == State.RUNNING_NORMAL
    assert app.acoustic_alert is False


def test_confirming_confirmer_idempotent():
    """CONFIRMING + CONFIRMER → CONFIRMING (transition idempotente)."""
    app = _make(State.CONFIRMING)
    app.transition(Event.CONFIRMER)
    assert app.state == State.CONFIRMING


# ---------------------------------------------------------------------------
# Transitions illégales (3)
# ---------------------------------------------------------------------------


def test_idle_baseline_done_raises():
    """IDLE + BASELINE_DONE → InvalidTransition (baseline non démarrée)."""
    app = AppState()
    with pytest.raises(InvalidTransition):
        app.transition(Event.BASELINE_DONE)


def test_idle_acoustic_warn_raises():
    """IDLE + ACOUSTIC_WARN → InvalidTransition (pas de baseline active)."""
    app = AppState()
    with pytest.raises(InvalidTransition):
        app.transition(Event.ACOUSTIC_WARN)


def test_baseline_capturing_path_blocked_raises():
    """BASELINE_CAPTURING + PATH_BLOCKED → InvalidTransition (vision non active)."""
    app = _make(State.BASELINE_CAPTURING)
    with pytest.raises(InvalidTransition):
        app.transition(Event.PATH_BLOCKED)
