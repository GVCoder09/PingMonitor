"""Reachability checks that run off the GUI thread."""

from collections.abc import Iterable
from typing import Optional

from PyQt5.QtCore import QObject, QRunnable, QThreadPool, pyqtSignal, pyqtSlot

from pingmonitor.monitor import host_is_reachable

UNREACHABLE = "host is unreachable"


class _Signals(QObject):
    done = pyqtSignal(int, str, object)  # generation, host, error or None


class _CheckTask(QRunnable):
    """Checks one host and reports through ``_Signals``."""

    def __init__(
        self, generation: int, host: str, timeout: int, signals: _Signals
    ) -> None:
        super().__init__()
        self._generation = generation
        self._host = host
        self._timeout = timeout
        self._signals = signals

    def run(self) -> None:
        """Ping the host once and emit the outcome."""
        try:
            error = (
                None if host_is_reachable(self._host, self._timeout) else UNREACHABLE
            )
        except Exception as exc:  # e.g. PermissionError without ICMP rights
            error = str(exc) or type(exc).__name__
        self._signals.done.emit(self._generation, self._host, error)


class HostChecker(QObject):
    """Checks several hosts concurrently without blocking the caller.

    Signals:
        finished(object): A ``dict`` mapping each host to None if it answered,
            or to a human-readable reason if it did not. Emitted once per call
            to ``check``; results of a superseded call are discarded.
    """

    finished = pyqtSignal(object)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        """Create an idle checker.

        Args:
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._signals = _Signals(self)
        self._signals.done.connect(self._on_done)
        self._generation = 0
        self._expected: tuple[str, ...] = ()
        self._results: dict[str, Optional[str]] = {}

    @property
    def is_busy(self) -> bool:
        """Whether a check is in progress."""
        return len(self._results) < len(self._expected)

    def check(self, hosts: Iterable[str], timeout: int = 3) -> None:
        """Start checking hosts; ``finished`` is emitted when all are done.

        Args:
            hosts: Hosts to check.
            timeout: Seconds to wait for each reply.
        """
        self._generation += 1
        self._expected = tuple(hosts)
        self._results = {}
        if not self._expected:
            self.finished.emit({})
            return
        pool = QThreadPool.globalInstance()
        for host in self._expected:
            pool.start(_CheckTask(self._generation, host, timeout, self._signals))

    @pyqtSlot(int, str, object)
    def _on_done(self, generation: int, host: str, error: Optional[str]) -> None:
        if generation != self._generation:
            return
        self._results[host] = error
        if len(self._results) == len(self._expected):
            self.finished.emit({h: self._results[h] for h in self._expected})
