from unittest.mock import patch

import pytest

from pingmonitor import monitor
from pingmonitor.monitor import PingMonitor, PingWorker
from pingmonitor.settings import PingSettings


def run_worker(worker, ping, stop_after=None):
    """Run a worker synchronously and return what it emitted."""
    results = []

    def collect(host, latency):
        results.append((host, latency))
        if stop_after is not None and len(results) >= stop_after:
            worker.stop()

    worker.ping_result.connect(collect)
    with patch.object(PingWorker, "_sleep"), patch.object(monitor, "ping", ping):
        worker.run()
    return results


def test_worker_maps_ping_results():
    """A timeout (None) and an error (False) both become None."""
    worker = PingWorker("example.test", PingSettings())
    calls = []

    def fake_ping(host, **kwargs):
        calls.append((host, kwargs))
        return [12.5, None, False][len(calls) - 1]

    results = run_worker(worker, fake_ping, stop_after=3)

    assert results == [
        ("example.test", 12.5),
        ("example.test", None),
        ("example.test", None),
    ]
    assert calls[0] == (
        "example.test",
        {"unit": "ms", "timeout": 3, "ttl": 56, "size": 32},
    )


def test_worker_picks_up_new_settings():
    worker = PingWorker("a.test", PingSettings())
    worker.update_settings(PingSettings(ttl=10))
    seen = []

    def fake_ping(host, **kwargs):
        seen.append(kwargs["ttl"])
        worker.stop()
        return 1.0

    run_worker(worker, fake_ping)
    assert seen == [10]


def test_worker_reports_exceptions_and_stops():
    worker = PingWorker("a.test", PingSettings())
    failures, finished = [], []
    worker.failed.connect(lambda host, msg: failures.append((host, msg)))
    worker.finished.connect(lambda: finished.append(True))

    def fake_ping(host, **kwargs):
        raise PermissionError("no raw sockets")

    results = run_worker(worker, fake_ping)

    assert results == []
    assert failures == [("a.test", "no raw sockets")]
    assert finished == [True]


def test_worker_does_not_emit_after_stop():
    worker = PingWorker("a.test", PingSettings())

    def fake_ping(host, **kwargs):
        worker.stop()  # stopped while the ping was in flight
        return 5.0

    assert run_worker(worker, fake_ping) == []


def test_host_is_reachable():
    with patch.object(monitor, "ping", return_value=None):
        assert monitor.host_is_reachable("slow.test")  # a timeout is not an error
    with patch.object(monitor, "ping", return_value=False):
        assert not monitor.host_is_reachable("bad.test")
    with patch.object(monitor, "ping", side_effect=PermissionError("nope")):
        with pytest.raises(PermissionError):
            monitor.host_is_reachable("any.test")


def test_monitor_pings_every_host_and_stops_without_blocking(qtbot):
    mon = PingMonitor()
    seen = {}
    mon.result.connect(lambda host, latency: seen.setdefault(host, latency))

    with patch.object(monitor, "ping", return_value=7.0):
        mon.start(["a.test", "b.test"], PingSettings())
        assert mon.is_running
        qtbot.waitUntil(lambda: len(seen) == 2, timeout=5000)
        mon.stop()
        assert not mon.is_running
        mon.shutdown()

    assert seen == {"a.test": 7.0, "b.test": 7.0}


def test_monitor_drops_results_of_stopped_workers(qtbot):
    mon = PingMonitor()
    seen = []
    mon.result.connect(lambda host, latency: seen.append(host))

    with patch.object(monitor, "ping", return_value=1.0):
        mon.start(["old.test"], PingSettings())
        qtbot.waitUntil(lambda: bool(seen), timeout=5000)
        mon.stop()
        seen.clear()
        mon.start(["new.test"], PingSettings())
        qtbot.waitUntil(lambda: "new.test" in seen, timeout=5000)
        mon.shutdown()

    assert "old.test" not in seen


def test_monitor_forwards_failures(qtbot):
    mon = PingMonitor()
    with patch.object(monitor, "ping", side_effect=PermissionError("denied")):
        with qtbot.waitSignal(mon.failed, timeout=5000) as blocker:
            mon.start(["a.test"], PingSettings())
        mon.shutdown()
    assert blocker.args == ["a.test", "denied"]
