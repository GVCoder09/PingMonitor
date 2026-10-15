import csv
import io
from datetime import datetime, timezone

from pingmonitor.history import HistoryLog


def read_rows(log):
    out = io.StringIO()
    log.write_csv(out)
    return list(csv.reader(io.StringIO(out.getvalue())))


def test_csv_export():
    log = HistoryLog()
    when = datetime(2026, 1, 2, 3, 4, 5, 678000, tzinfo=timezone.utc)
    log.record("a.test", 12.3456, when)
    log.record("a.test", None, when)

    rows = read_rows(log)

    assert rows[0] == ["timestamp", "host", "latency_ms", "status"]
    assert rows[1] == ["2026-01-02T03:04:05.678+00:00", "a.test", "12.346", "ok"]
    assert rows[2] == ["2026-01-02T03:04:05.678+00:00", "a.test", "", "lost"]


def test_capacity_drops_oldest():
    log = HistoryLog(max_samples=2)
    for i in range(3):
        log.record(f"h{i}", 1.0)
    assert [row[1] for row in read_rows(log)[1:]] == ["h1", "h2"]


def test_clear_and_len():
    log = HistoryLog()
    log.record("a", 1.0)
    assert len(log) == 1
    log.clear()
    assert len(log) == 0
