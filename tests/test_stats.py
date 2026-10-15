import pytest

from pingmonitor.stats import PERCENTILE_WINDOW, PingStats, percentile


def test_empty_stats():
    stats = PingStats()
    assert stats.sent == 0
    assert stats.received == 0
    assert stats.avg == 0
    assert stats.loss_percent == 0
    assert stats.jitter == 0
    assert stats.median == 0
    assert stats.p95 == 0


def test_record_updates_min_max_avg():
    stats = PingStats()
    for latency in (10.0, 30.0, 20.0):
        stats.record(latency)
    assert stats.sent == stats.received == 3
    assert stats.min == 10.0
    assert stats.max == 30.0
    assert stats.avg == pytest.approx(20.0)


def test_lost_packets_count_as_loss_only():
    stats = PingStats()
    stats.record(40.0)
    stats.record(None)
    assert stats.sent == 2
    assert stats.received == 1
    assert stats.loss_percent == pytest.approx(50.0)
    assert stats.min == stats.max == stats.avg == 40.0


def test_zero_latency_is_a_valid_reply():
    stats = PingStats()
    stats.record(0.0)
    assert stats.received == 1
    assert stats.loss_percent == 0


def test_jitter_is_mean_absolute_difference_of_consecutive_replies():
    stats = PingStats()
    for latency in (10.0, 20.0, 15.0):  # differences: 10, 5
        stats.record(latency)
    assert stats.jitter == pytest.approx(7.5)


def test_jitter_skips_lost_packets():
    stats = PingStats()
    for latency in (10.0, None, 30.0):
        stats.record(latency)
    assert stats.jitter == pytest.approx(20.0)


def test_median_and_p95():
    stats = PingStats()
    for latency in range(1, 101):
        stats.record(float(latency))
    assert stats.median == pytest.approx(50.5)
    assert stats.p95 == pytest.approx(95.05)


def test_percentile_window_is_bounded():
    stats = PingStats()
    for latency in range(PERCENTILE_WINDOW + 500):
        stats.record(float(latency))
    # Only the newest PERCENTILE_WINDOW replies count.
    assert stats.median == pytest.approx(500 + (PERCENTILE_WINDOW - 1) / 2)
    assert stats.received == PERCENTILE_WINDOW + 500


def test_percentile_edges():
    assert percentile([], 50) == 0
    assert percentile([7.0], 95) == 7.0
    assert percentile([1.0, 3.0], 0) == 1.0
    assert percentile([1.0, 3.0], 100) == 3.0
    assert percentile([1.0, 3.0], 50) == 2.0


def test_reset():
    stats = PingStats()
    stats.record(5.0)
    stats.record(9.0)
    stats.reset()
    assert stats.sent == 0
    assert stats.min == float("inf")
    assert stats.jitter == 0
    assert stats.median == 0
