"""Detection of connection loss, recovery and slow replies."""

from dataclasses import dataclass
from enum import Enum
from typing import Optional

LOSS_STREAK = 3
"""Consecutive lost packets after which a host is considered down."""


class AlertKind(Enum):
    """What happened to a host."""

    DOWN = "down"
    UP = "up"
    SLOW = "slow"


@dataclass(frozen=True)
class Alert:
    """A state change worth telling the user about.

    Attributes:
        host: The affected host.
        kind: What happened.
        latency: The reply that triggered the alert, or None for ``DOWN``.
    """

    host: str
    kind: AlertKind
    latency: Optional[float] = None


class _HostState:
    def __init__(self) -> None:
        self.losses = 0
        self.down = False
        self.slow = False


class AlertTracker:
    """Turns a stream of results into edge-triggered alerts.

    An alert is produced only when the state changes: a host goes down after
    ``LOSS_STREAK`` lost packets in a row, comes back on the first reply, and
    becomes slow when a reply exceeds the threshold.
    """

    def __init__(self, loss_streak: int = LOSS_STREAK) -> None:
        """Create a tracker.

        Args:
            loss_streak: Consecutive losses that mark a host as down.
        """
        self._loss_streak = loss_streak
        self._states: dict[str, _HostState] = {}

    def reset(self) -> None:
        """Forget the state of every host."""
        self._states.clear()

    def is_alerting(self, host: str) -> bool:
        """Return whether the host is currently down or slow.

        Args:
            host: The host to query.
        """
        state = self._states.get(host)
        return bool(state and (state.down or state.slow))

    def record(
        self, host: str, latency: Optional[float], threshold_ms: int = 0
    ) -> Optional[Alert]:
        """Feed one result and return an alert if the state changed.

        Args:
            host: The pinged host.
            latency: Round-trip time in milliseconds, or None if lost.
            threshold_ms: Latency above which a reply is slow; 0 disables.

        Returns:
            The alert, or None if nothing changed.
        """
        state = self._states.setdefault(host, _HostState())

        if latency is None:
            state.losses += 1
            if state.losses >= self._loss_streak and not state.down:
                state.down = True
                state.slow = False
                return Alert(host, AlertKind.DOWN)
            return None

        state.losses = 0
        was_down, state.down = state.down, False
        slow = threshold_ms > 0 and latency > threshold_ms
        was_slow, state.slow = state.slow, slow
        if was_down:
            return Alert(host, AlertKind.UP, latency)
        if slow and not was_slow:
            return Alert(host, AlertKind.SLOW, latency)
        return None
