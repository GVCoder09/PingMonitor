from unittest.mock import patch

from pingmonitor import hostcheck
from pingmonitor.hostcheck import UNREACHABLE, HostChecker


def test_reports_reachable_unreachable_and_errors(qtbot):
    def fake(host, timeout):
        if host == "boom.test":
            raise PermissionError("denied")
        return host == "ok.test"

    checker = HostChecker()
    with patch.object(hostcheck, "host_is_reachable", fake):
        with qtbot.waitSignal(checker.finished, timeout=5000) as blocker:
            checker.check(["ok.test", "bad.test", "boom.test"])

    assert blocker.args[0] == {
        "ok.test": None,
        "bad.test": UNREACHABLE,
        "boom.test": "denied",
    }
    assert not checker.is_busy


def test_empty_check_finishes_immediately(qtbot):
    checker = HostChecker()
    with qtbot.waitSignal(checker.finished, timeout=1000) as blocker:
        checker.check([])
    assert blocker.args[0] == {}


def test_superseded_check_is_discarded(qtbot):
    checker = HostChecker()
    results = []
    checker.finished.connect(results.append)
    with patch.object(hostcheck, "host_is_reachable", lambda host, timeout: True):
        checker.check(["old.test"])
        checker.check(["new.test"])
        qtbot.waitUntil(lambda: bool(results), timeout=5000)
        qtbot.wait(200)
    assert results == [{"new.test": None}]
