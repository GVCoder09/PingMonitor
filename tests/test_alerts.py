from pingmonitor.alerts import (
    LOSS_STREAK,
    Alert,
    AlertKind,
    AlertThrottle,
    AlertTracker,
)


def feed(tracker, values, threshold=0):
    return [tracker.record("h", v, threshold) for v in values]


def kinds(alerts):
    return [a.kind if a else None for a in alerts]


def test_down_after_loss_streak_then_up_on_first_reply():
    tracker = AlertTracker()
    results = feed(tracker, [None] * LOSS_STREAK + [None, 10.0])
    assert kinds(results) == (
        [None] * (LOSS_STREAK - 1) + [AlertKind.DOWN, None, AlertKind.UP]
    )
    assert not tracker.is_alerting("h")


def test_short_loss_streak_is_ignored():
    tracker = AlertTracker()
    assert feed(tracker, [None, None, 10.0, None, None, 10.0]) == [None] * 6


def test_slow_alert_fires_once_per_episode():
    tracker = AlertTracker()
    results = feed(tracker, [10.0, 200.0, 300.0, 10.0, 250.0], threshold=100)
    assert kinds(results) == [None, AlertKind.SLOW, None, None, AlertKind.SLOW]
    assert results[1].latency == 200.0


def test_slow_is_disabled_with_zero_threshold():
    tracker = AlertTracker()
    assert feed(tracker, [5000.0], threshold=0) == [None]


def test_is_alerting_tracks_down_and_slow():
    tracker = AlertTracker()
    feed(tracker, [200.0], threshold=100)
    assert tracker.is_alerting("h")
    feed(tracker, [10.0], threshold=100)
    assert not tracker.is_alerting("h")
    feed(tracker, [None] * LOSS_STREAK)
    assert tracker.is_alerting("h")


def test_hosts_are_independent_and_reset_clears():
    tracker = AlertTracker()
    for _ in range(LOSS_STREAK):
        tracker.record("a", None)
    assert tracker.is_alerting("a")
    assert not tracker.is_alerting("b")
    tracker.reset()
    assert not tracker.is_alerting("a")


class FakeClock:
    def __init__(self):
        self.now = 1000.0

    def __call__(self):
        return self.now


def test_throttle_suppresses_repeats_within_cooldown():
    clock = FakeClock()
    throttle = AlertThrottle(cooldown=60, clock=clock)
    slow = Alert("h", AlertKind.SLOW, 200.0)
    assert throttle.allow(slow)
    clock.now += 59
    assert not throttle.allow(slow)
    clock.now += 2
    assert throttle.allow(slow)


def test_throttle_is_per_host_and_kind():
    throttle = AlertThrottle(cooldown=60, clock=FakeClock())
    assert throttle.allow(Alert("a", AlertKind.SLOW, 1.0))
    assert throttle.allow(Alert("b", AlertKind.SLOW, 1.0))
    assert throttle.allow(Alert("a", AlertKind.DOWN))


def test_throttle_reports_recovery_only_after_an_announced_outage():
    clock = FakeClock()
    throttle = AlertThrottle(cooldown=60, clock=clock)
    up = Alert("h", AlertKind.UP, 5.0)
    assert not throttle.allow(up)  # never announced as down
    assert throttle.allow(Alert("h", AlertKind.DOWN))
    assert throttle.allow(up)
    assert not throttle.allow(up)  # already reported


def test_throttle_silences_a_flapping_connection():
    clock = FakeClock()
    throttle = AlertThrottle(cooldown=60, clock=clock)
    shown = 0
    for _ in range(10):  # down, up, down, up ... every 5 seconds
        shown += throttle.allow(Alert("h", AlertKind.DOWN))
        clock.now += 5
        shown += throttle.allow(Alert("h", AlertKind.UP, 5.0))
        clock.now += 5
    assert shown == 4  # a down/up pair at t=0 and another at t=60


def test_throttle_reset():
    throttle = AlertThrottle(cooldown=60, clock=FakeClock())
    assert throttle.allow(Alert("h", AlertKind.DOWN))
    throttle.reset()
    assert throttle.allow(Alert("h", AlertKind.DOWN))
