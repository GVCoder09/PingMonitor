"""Background pinging: one worker thread per host and the controller above them."""

from collections.abc import Iterable
from dataclasses import dataclass
from typing import Optional

from ping3 import ping
from PyQt5.QtCore import (
    QMutex,
    QMutexLocker,
    QObject,
    QThread,
    pyqtSignal,
    pyqtSlot,
)

from pingmonitor.settings import PingSettings

SHUTDOWN_WAIT_MS = 5000
"""How long ``PingMonitor.shutdown`` waits for each thread before killing it."""


class PingWorker(QObject):
    """Pings one host in a loop until stopped; meant to live in a ``QThread``.

    Signals:
        ping_result(str, object): Host and latency in milliseconds, or None
            for a lost packet.
        failed(str, str): Host and an error message; the loop ends after it.
        finished: The loop has ended, for whatever reason.
    """

    ping_result = pyqtSignal(str, object)
    failed = pyqtSignal(str, str)
    finished = pyqtSignal()

    def __init__(self, host: str, settings: PingSettings) -> None:
        """Create a worker.

        Args:
            host: Hostname or IP address to ping.
            settings: Initial ping parameters.
        """
        super().__init__()
        self.host = host
        self._settings = settings
        self._lock = QMutex()
        self._running = True

    def update_settings(self, settings: PingSettings) -> None:
        """Replace the ping parameters in a thread-safe way.

        The new values apply from the next ping.

        Args:
            settings: New ping parameters.
        """
        with QMutexLocker(self._lock):
            self._settings = settings

    def run(self) -> None:
        """Ping every ``interval`` seconds until stopped or an error occurs."""
        while self._running:
            with QMutexLocker(self._lock):
                s = self._settings
            try:
                # ping3 returns None on timeout and False on a network error.
                latency = ping(
                    self.host, unit="ms", timeout=s.timeout, ttl=s.ttl, size=s.size
                )
            except Exception as exc:  # e.g. PermissionError without ICMP rights
                if self._running:
                    self.failed.emit(self.host, str(exc) or type(exc).__name__)
                break
            if not self._running:
                break
            self.ping_result.emit(self.host, latency if latency else None)
            self._sleep(s.interval * 1000)
        self.finished.emit()

    def stop(self) -> None:
        """Ask the ``run`` loop to finish; it never blocks."""
        self._running = False

    def _sleep(self, ms: int, step: int = 100) -> None:
        """Sleep in short slices so that ``stop`` takes effect quickly."""
        while ms > 0 and self._running:
            QThread.msleep(min(step, ms))
            ms -= step


@dataclass(eq=False)
class _Job:
    """A worker together with the thread it runs in."""

    thread: QThread
    worker: PingWorker


class PingMonitor(QObject):
    """Owns one worker thread per host; the single entry point for pinging.

    Stopping is asynchronous: ``stop`` returns immediately and the threads wind
    down in the background, so the GUI never freezes waiting for a slow ping.
    Call ``shutdown`` once before the application exits.

    Signals:
        result(str, object): Host and latency (None if lost), forwarded from
            the active workers.
        failed(str, str): Host and error message, forwarded from the active
            workers.
    """

    result = pyqtSignal(str, object)
    failed = pyqtSignal(str, str)

    def __init__(self, parent: Optional[QObject] = None) -> None:
        """Create an idle monitor.

        Args:
            parent: Optional Qt parent.
        """
        super().__init__(parent)
        self._active: list[_Job] = []
        # Jobs that were asked to stop but may still be inside a ping(). They
        # stay referenced so that Qt never destroys a running QThread.
        self._retiring: set[_Job] = set()

    @property
    def is_running(self) -> bool:
        """Whether monitoring is currently active."""
        return bool(self._active)

    def start(self, hosts: Iterable[str], settings: PingSettings) -> None:
        """(Re)start monitoring.

        Args:
            hosts: Hosts to ping, one thread each.
            settings: Ping parameters to start with.
        """
        self.stop()
        for host in hosts:
            job = _Job(QThread(), PingWorker(host, settings))
            job.worker.moveToThread(job.thread)
            job.worker.ping_result.connect(self._on_result)
            job.worker.failed.connect(self._on_failed)
            job.worker.finished.connect(job.thread.quit)
            job.thread.started.connect(job.worker.run)
            job.thread.finished.connect(lambda job=job: self._retiring.discard(job))
            self._active.append(job)
            job.thread.start()

    def stop(self) -> None:
        """Ask every worker to finish and return immediately; no-op if idle."""
        for job in self._active:
            job.worker.stop()
            self._retiring.add(job)
        self._active.clear()

    def shutdown(self) -> None:
        """Stop and block until all threads have ended; call on application exit."""
        self.stop()
        for job in list(self._retiring):
            job.thread.quit()
            if not job.thread.wait(SHUTDOWN_WAIT_MS):
                job.thread.terminate()
                job.thread.wait()
        self._retiring.clear()

    def update_settings(self, settings: PingSettings) -> None:
        """Pass new parameters to the running workers; no-op if idle.

        Args:
            settings: New ping parameters.
        """
        for job in self._active:
            job.worker.update_settings(settings)

    def _sender_is_active(self) -> bool:
        return any(job.worker is self.sender() for job in self._active)

    @pyqtSlot(str, object)
    def _on_result(self, host: str, latency: Optional[float]) -> None:
        if self._sender_is_active():
            self.result.emit(host, latency)

    @pyqtSlot(str, str)
    def _on_failed(self, host: str, message: str) -> None:
        if self._sender_is_active():
            self.failed.emit(host, message)


def host_is_reachable(host: str, timeout: int = 3) -> bool:
    """Check a host with a single blocking ping.

    Args:
        host: Hostname or IP address.
        timeout: Seconds to wait for the reply.

    Returns:
        False only if the ping failed with an error (for example, the name does
        not resolve). A plain timeout is not treated as an error.

    Raises:
        Exception: Whatever ``ping3`` raises, e.g. ``PermissionError`` when ICMP
            sockets are not allowed.
    """
    return ping(host, unit="ms", timeout=timeout) is not False
