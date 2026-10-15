from unittest.mock import patch

import pytest
from PyQt5.QtCore import QSettings
from PyQt5.QtGui import QColor

from pingmonitor import hostcheck, monitor
from pingmonitor.settings import AppConfig, PingSettings
from pingmonitor.stats import PingStats
from pingmonitor.store import SettingsStore
from pingmonitor.ui.controls_panel import ControlsPanel
from pingmonitor.ui.main_window import Mode, PingWindow
from pingmonitor.ui.mini_window import MiniWindow
from pingmonitor.ui.ping_plot import PingPlot, nice_step
from pingmonitor.ui.stats_panel import StatsPanel


@pytest.fixture
def store(tmp_path):
    return SettingsStore(QSettings(str(tmp_path / "s.ini"), QSettings.IniFormat))


@pytest.fixture
def window(qtbot, store):
    win = PingWindow(store)
    qtbot.addWidget(win)
    yield win
    win._monitor.shutdown()


def test_nice_step():
    assert nice_step(100) == 20
    assert nice_step(7) == 2
    assert nice_step(0.3) == pytest.approx(0.1)
    assert nice_step(1000) == 200


def test_controls_panel_roundtrip(qtbot):
    config = AppConfig(
        hosts=("a.test", "b.test"),
        ping=PingSettings(ttl=9, timeout=2, size=40, interval=4),
        max_points=33,
        alert_ms=150,
    )
    panel = ControlsPanel(config)
    qtbot.addWidget(panel)
    assert panel.hosts() == ("a.test", "b.test")
    assert panel.settings() == config.ping
    assert panel.max_points() == 33
    assert panel.alert_ms() == 150


def test_controls_panel_empty_fields_use_defaults(qtbot):
    panel = ControlsPanel(AppConfig())
    qtbot.addWidget(panel)
    panel.ttl_input.setText("")
    panel.alert_input.setText("")
    assert panel.settings().ttl == PingSettings().ttl
    assert panel.alert_ms() == 0


def test_controls_panel_signals_and_busy_state(qtbot):
    panel = ControlsPanel(AppConfig())
    qtbot.addWidget(panel)
    with qtbot.waitSignal(panel.max_points_changed) as blocker:
        panel.points_input.setText("25")
    assert blocker.args == [25]
    with qtbot.waitSignal(panel.alert_changed) as blocker:
        panel.alert_input.setText("80")
    assert blocker.args == [80]

    panel.set_busy(True)
    assert not panel.apply_btn.isEnabled()
    assert not panel.start_btn.isEnabled()
    panel.set_busy(False)
    panel.set_running(True)
    assert panel.stop_btn.isEnabled()
    assert not panel.start_btn.isEnabled()


def test_stats_panel_rows(qtbot):
    panel = StatsPanel()
    qtbot.addWidget(panel)
    panel.set_hosts(["a.test", "b.test"])
    stats = PingStats()
    for latency in (10.0, None, 30.0):
        stats.record(latency)
    panel.show_stats("a.test", stats)
    panel.show_stats("unknown.test", stats)  # ignored

    cells = [c.text() for c in panel._cells["a.test"]]
    assert cells[:5] == ["a.test", "3", "2", "33.3%", "10.0 ms"]
    assert [c.text() for c in panel._cells["b.test"]][1:4] == ["0", "0", "0.0%"]
    assert panel._cells["b.test"][4].text() == "-"

    panel.set_hosts(["only.test"])
    assert list(panel._cells) == ["only.test"]


def test_plot_paints_series_losses_and_alert_line(qtbot):
    plot = PingPlot(max_points=10)
    qtbot.addWidget(plot)
    plot.resize(400, 250)
    plot.set_hosts(["a.test", "b.test"])
    plot.set_alert_ms(80)
    for i in range(6):
        plot.add("a.test", None if i == 3 else 10.0 + i)
        plot.add("b.test", 40.0)
    plot.add("unknown.test", 1.0)  # ignored
    image = plot.grab().toImage()
    assert not image.isNull()
    colors = {
        image.pixelColor(x, y).name()
        for x in range(0, 400, 7)
        for y in range(0, 250, 7)
    }
    assert len(colors) > 3  # more than just the background was drawn

    plot.set_max_points(3)
    assert all(len(s) <= 3 for s in plot._series.values())
    plot.clear()
    assert all(len(s) == 0 for s in plot._series.values())


def test_plot_handles_tiny_size_and_no_hosts(qtbot):
    plot = PingPlot(max_points=1)
    qtbot.addWidget(plot)
    plot.resize(20, 20)
    assert not plot.grab().isNull()


def test_mini_window_colors(qtbot):
    mini = MiniWindow()
    qtbot.addWidget(mini)
    stats = PingStats()
    stats.record(20.0)
    mini.show_state(20.0, stats, alerting=False)
    assert mini._color == QColor(80, 220, 100)
    mini.show_state(100.0, stats, alerting=False)
    assert mini._color == QColor(240, 200, 60)
    mini.show_state(20.0, stats, alerting=True)
    assert mini._color == QColor(240, 80, 80)
    mini.show_state(None, stats, alerting=False)
    assert mini._headline == "×"
    assert not mini.grab().isNull()


def test_window_collects_results_and_exports_csv(window, tmp_path):
    window._reset_hosts(("a.test",))
    window._on_ping_result("a.test", 12.0)
    window._on_ping_result("a.test", None)
    window._on_ping_result("other.test", 1.0)  # not monitored: ignored

    assert window._stats["a.test"].sent == 2
    assert len(window._history) == 2
    assert "a.test: lost" in window._tray.toolTip()

    path = tmp_path / "out.csv"
    with patch(
        "pingmonitor.ui.main_window.QFileDialog.getSaveFileName",
        return_value=(str(path), ""),
    ):
        window.export_csv()
    lines = path.read_text(encoding="utf-8").splitlines()
    assert lines[0] == "timestamp,host,latency_ms,status"
    assert len(lines) == 3


def test_window_alerts_switch_tray_icon(window):
    window._reset_hosts(("a.test",))
    with patch.object(window._tray, "showMessage") as notify:
        for _ in range(3):
            window._on_ping_result("a.test", None)
    assert window._tray_alerting
    if window._tray.isVisible():
        assert notify.called
    window._on_ping_result("a.test", 5.0)
    assert not window._tray_alerting


def test_window_mode_cycle(window):
    window.show()
    window.set_mode(Mode.COMPACT)
    assert not window._controls.isVisible()
    assert not window.menuBar().isVisible()
    window.set_mode(Mode.NORMAL)
    assert window._controls.isVisible()
    if window._tray_available:
        window.set_mode(Mode.MINI)
        assert window._mini.isVisible() and not window.isVisible()
        window.set_mode(Mode.NORMAL)
        assert window.isVisible() and not window._mini.isVisible()


def test_window_persists_settings(qtbot, store):
    win = PingWindow(store)
    qtbot.addWidget(win)
    win._controls.points_input.setText("42")
    win._controls.alert_input.setText("90")
    win._controls.ttl_input.setText("12")
    win.close()
    win._monitor.shutdown()

    config = store.load()
    assert config.max_points == 42
    assert config.alert_ms == 90
    assert config.ping.ttl == 12


def test_window_applies_reachable_hosts_only(window, qtbot):
    def fake(host, timeout):
        return host != "bad.test"

    window._controls.hosts_input.setText("ok.test, bad.test")
    with patch.object(hostcheck, "host_is_reachable", fake):
        with patch("pingmonitor.ui.main_window.QMessageBox.warning") as warn:
            window.apply_hosts()
            qtbot.waitUntil(lambda: window._hosts == ("ok.test",), timeout=5000)
    assert warn.called
    assert window._controls.hosts() == ("ok.test",)
    assert not window._monitor.is_running  # Apply alone does not start


def test_window_start_and_stop(window, qtbot):
    window._controls.hosts_input.setText("ok.test")
    with patch.object(hostcheck, "host_is_reachable", lambda h, t: True):
        with patch.object(monitor, "ping", return_value=3.0):
            window.start_monitoring()
            qtbot.waitUntil(lambda: window._monitor.is_running, timeout=5000)
            qtbot.waitUntil(lambda: window._stats["ok.test"].received > 0, timeout=5000)
            window.stop_monitoring()
            window._monitor.shutdown()
    assert not window._monitor.is_running
    assert window._controls.start_btn.isEnabled()


def test_window_shows_error_when_pinging_fails(window, qtbot):
    window._controls.hosts_input.setText("8.8.8.8")  # unchanged: no host check
    with patch.object(monitor, "ping", side_effect=PermissionError("denied")):
        with patch("pingmonitor.ui.main_window.QMessageBox.critical") as critical:
            window.start_monitoring()
            qtbot.waitUntil(lambda: critical.called, timeout=5000)
            window._monitor.shutdown()
    assert "denied" in critical.call_args[0][2]
    assert not window._monitor.is_running


def test_compact_mode_has_its_nominal_size(window, qtbot):
    from pingmonitor.ui.main_window import COMPACT_SIZE, NORMAL_SIZE

    window.show()
    window.set_mode(Mode.COMPACT)
    qtbot.wait(50)
    assert (window.width(), window.height()) == COMPACT_SIZE
    window.set_mode(Mode.NORMAL)
    qtbot.wait(50)
    assert (window.width(), window.height()) == NORMAL_SIZE


def test_first_host_keeps_the_classic_palette():
    from pingmonitor.ui.colors import MEAN_COLOR, series_color

    assert series_color(0) == QColor("red")
    assert MEAN_COLOR == QColor("green")  # matplotlib's "green" is #008000
    assert len({series_color(i).name() for i in range(8)}) == 8
