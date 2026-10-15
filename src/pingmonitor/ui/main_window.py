"""Main window: wires the panels, the monitor and the window modes together."""

from enum import Enum
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import (
    QAction,
    QActionGroup,
    QApplication,
    QFileDialog,
    QMainWindow,
    QMenu,
    QMessageBox,
    QSystemTrayIcon,
    QVBoxLayout,
    QWidget,
)

from pingmonitor.alerts import Alert, AlertKind, AlertThrottle, AlertTracker
from pingmonitor.history import HistoryLog
from pingmonitor.hostcheck import HostChecker
from pingmonitor.monitor import PingMonitor
from pingmonitor.resources import alert_icon, app_icon
from pingmonitor.settings import AppConfig
from pingmonitor.stats import PingStats
from pingmonitor.store import SettingsStore
from pingmonitor.ui.controls_panel import ControlsPanel
from pingmonitor.ui.mini_window import MiniWindow
from pingmonitor.ui.ping_plot import PingPlot
from pingmonitor.ui.stats_panel import StatsPanel

TITLE = "Ping Monitor"
NORMAL_SIZE = (980, 640)
COMPACT_SIZE = (400, 300)
COMPACT_OPACITY = 0.8
MINI_OPACITIES = (0.25, 0.5, 0.75, 1.0)
NOTIFICATION_MS = 5000


class Mode(Enum):
    """Display mode of the application."""

    NORMAL = "normal"
    COMPACT = "compact"
    MINI = "mini"


class PingWindow(QMainWindow):
    """Main application window.

    Switches between three modes (see ``Mode``): the full window, a frameless
    translucent compact window, and a tiny click-through ``MiniWindow`` that is
    controlled from the system tray. It also owns the monitoring state: the
    statistics, the history and the alerts of every host.
    """

    def __init__(self, store: Optional[SettingsStore] = None) -> None:
        """Create the window with all its panels, in normal mode.

        Args:
            store: Where the configuration is loaded from and saved to;
                defaults to the per-user application settings.
        """
        super().__init__()
        self.setWindowTitle(TITLE)
        self.setWindowIcon(app_icon())
        self.resize(*NORMAL_SIZE)
        QApplication.setStyle("Fusion")
        QApplication.setPalette(QApplication.style().standardPalette())

        self._store = store or SettingsStore()
        config = self._store.load()
        self._hosts: tuple[str, ...] = config.hosts
        self._ping_settings = config.ping
        self._max_points = config.max_points
        self._alert_ms = config.alert_ms
        self._notifications = config.notifications
        self._mini_opacity = config.mini_opacity

        self._stats: dict[str, PingStats] = {}
        self._last_latency: dict[str, Optional[float]] = {}
        self._history = HistoryLog()
        self._alerts = AlertTracker()
        self._throttle = AlertThrottle()
        self._monitor = PingMonitor(self)
        self._checker = HostChecker(self)
        self._pending_start = False
        self._mode = Mode.NORMAL
        self._drag_offset = None

        self._controls = ControlsPanel(config)
        self._plot = PingPlot(config.max_points)
        self._stats_panel = StatsPanel()
        self._mini = MiniWindow()
        self._tray_available = QSystemTrayIcon.isSystemTrayAvailable()
        self._tray = QSystemTrayIcon(app_icon(), self)
        self._tray_alerting = False

        self._build_layout()
        self._build_actions()
        self._build_menus()
        self._build_tray_menu()
        self._connect_signals()

        self._plot.set_alert_ms(self._alert_ms)
        self._mini.set_opacity(self._mini_opacity)
        self._reset_hosts(self._hosts)
        if self._tray_available:
            self._tray.show()
        else:
            self._controls.mini_btn.setEnabled(False)

    # --- construction -------------------------------------------------

    def _build_layout(self) -> None:
        layout = QVBoxLayout()
        layout.addWidget(self._controls)
        layout.addWidget(self._plot, stretch=1)
        layout.addWidget(self._stats_panel)
        central = QWidget()
        central.setLayout(layout)
        self.setCentralWidget(central)

    def _build_actions(self) -> None:
        self._act_export = QAction("Export history to CSV...", self)
        self._act_export.triggered.connect(self.export_csv)
        self._act_image = QAction("Save graph as image...", self)
        self._act_image.triggered.connect(self.save_graph_image)
        self._act_quit = QAction("Quit", self, shortcut="Ctrl+Q")
        self._act_quit.triggered.connect(QApplication.quit)
        self._act_compact = QAction("Compact mode", self, shortcut="Ctrl+W")
        self._act_compact.triggered.connect(self.toggle_compact_mode)
        self._act_mini = QAction("Mini mode", self, shortcut="Ctrl+E")
        self._act_mini.triggered.connect(lambda: self.set_mode(Mode.MINI))
        # Window actions double as the context menu, which stays usable in
        # compact mode where the menu bar is hidden.
        for action in (
            self._act_compact,
            self._act_mini,
            self._act_export,
            self._act_image,
            self._act_quit,
        ):
            self.addAction(action)
        self.setContextMenuPolicy(Qt.ActionsContextMenu)

    def _build_menus(self) -> None:
        file_menu = self.menuBar().addMenu("&File")
        file_menu.addAction(self._act_export)
        file_menu.addAction(self._act_image)
        file_menu.addSeparator()
        file_menu.addAction(self._act_quit)
        view_menu = self.menuBar().addMenu("&View")
        view_menu.addAction(self._act_compact)
        view_menu.addAction(self._act_mini)

    def _build_tray_menu(self) -> None:
        """Create the tray menu, the only way to control the mini window."""
        menu = QMenu()
        menu.addAction("Show window", lambda: self.set_mode(Mode.NORMAL))
        menu.addAction("Compact mode", lambda: self.set_mode(Mode.COMPACT))
        menu.addAction("Mini mode", lambda: self.set_mode(Mode.MINI))
        menu.addSeparator()
        self._move_action = menu.addAction("Move mini window")
        self._move_action.setCheckable(True)
        self._move_action.toggled.connect(self._mini.set_movable)

        opacity_menu = menu.addMenu("Mini window opacity")
        group = QActionGroup(opacity_menu)
        for value in MINI_OPACITIES:
            action = opacity_menu.addAction(f"{value:.0%}")
            action.setCheckable(True)
            action.setChecked(abs(value - self._mini_opacity) < 0.01)
            action.triggered.connect(lambda _checked, v=value: self._set_opacity(v))
            group.addAction(action)

        menu.addSeparator()
        menu.addAction("Quit", QApplication.quit)
        self._tray.setContextMenu(menu)
        self._tray.activated.connect(self._on_tray_activated)
        self._tray_menu = menu

    def _connect_signals(self) -> None:
        c = self._controls
        c.start_requested.connect(self.start_monitoring)
        c.stop_requested.connect(self.stop_monitoring)
        c.compact_requested.connect(self.toggle_compact_mode)
        c.mini_requested.connect(lambda: self.set_mode(Mode.MINI))
        c.hosts_applied.connect(self.apply_hosts)
        c.params_changed.connect(self._apply_params)
        c.max_points_changed.connect(self._on_max_points_changed)
        c.alert_changed.connect(self._on_alert_changed)
        c.notifications_changed.connect(self._on_notifications_changed)
        self._monitor.result.connect(self._on_ping_result)
        self._monitor.failed.connect(self._on_monitor_failed)
        self._checker.finished.connect(self._on_hosts_checked)
        self._mini.moved.connect(self._on_mini_moved)
        QApplication.instance().aboutToQuit.connect(self._monitor.shutdown)

    # --- hosts --------------------------------------------------------

    def _reset_hosts(self, hosts: tuple[str, ...]) -> None:
        """Switch to a new set of hosts with fresh statistics and graph."""
        self._hosts = hosts
        self._stats = {host: PingStats() for host in hosts}
        self._last_latency = {}
        self._alerts.reset()
        self._throttle.reset()
        self._plot.set_hosts(hosts)
        self._stats_panel.set_hosts(hosts)
        self._mini.reset()
        self._update_tray()
        if self._mode is Mode.COMPACT:
            self.setWindowTitle(self._compact_title())

    def _compact_title(self) -> str:
        return f"Ping: {', '.join(self._hosts)}"

    def start_monitoring(self) -> None:
        """Check the hosts from the field if they changed, then start pinging."""
        self._request_hosts(start=True)

    def apply_hosts(self) -> None:
        """Check and apply the hosts from the field without starting."""
        self._request_hosts(start=False)

    def _request_hosts(self, start: bool) -> None:
        hosts = self._controls.hosts()
        if not hosts:
            return
        if hosts == self._hosts:
            if start:
                self._begin_monitoring()
            return
        # A running monitor is restarted on the new hosts once they pass.
        self._pending_start = start or self._monitor.is_running
        self._controls.set_busy(True)
        self._checker.check(hosts, self._ping_settings.timeout)

    def _on_hosts_checked(self, results: dict[str, Optional[str]]) -> None:
        self._controls.set_busy(False)
        failures = {host: error for host, error in results.items() if error}
        reachable = tuple(host for host, error in results.items() if not error)
        if failures:
            details = "\n".join(f"{host}: {error}" for host, error in failures.items())
            QMessageBox.warning(self, "Error", f"Cannot connect to:\n{details}")
        if not reachable:
            self._pending_start = False
            return
        self._controls.set_hosts(reachable)
        self._reset_hosts(reachable)
        self._save_config()
        if self._pending_start:
            self._begin_monitoring()
        self._pending_start = False

    # --- monitoring ---------------------------------------------------

    def _begin_monitoring(self) -> None:
        self._monitor.start(self._hosts, self._ping_settings)
        self._controls.set_running(True)

    def stop_monitoring(self) -> None:
        """Stop pinging; returns immediately, threads finish in the background."""
        self._pending_start = False
        self._monitor.stop()
        self._controls.set_running(False)

    def _on_monitor_failed(self, host: str, message: str) -> None:
        self.stop_monitoring()
        QMessageBox.critical(self, "Error", f"Cannot ping {host}:\n{message}")

    def _on_ping_result(self, host: str, latency: Optional[float]) -> None:
        stats = self._stats.get(host)
        if stats is None:
            return
        stats.record(latency)
        self._last_latency[host] = latency
        self._history.record(host, latency)
        self._plot.add(host, latency)
        self._stats_panel.show_stats(host, stats)

        alert = self._alerts.record(host, latency, self._alert_ms)
        if alert is not None:
            self._notify(alert)
        if host == self._hosts[0]:
            self._mini.show_state(latency, stats, self._alerts.is_alerting(host))
        self._update_tray()

    # --- alerts and tray ----------------------------------------------

    def _notify(self, alert: Alert) -> None:
        if not self._notifications or not self._throttle.allow(alert):
            return
        if alert.kind is AlertKind.DOWN:
            text, icon = f"{alert.host} is not responding", QSystemTrayIcon.Warning
        elif alert.kind is AlertKind.UP:
            text, icon = f"{alert.host} is back online", QSystemTrayIcon.Information
        else:
            text = f"{alert.host}: {alert.latency:.0f} ms is above {self._alert_ms} ms"
            icon = QSystemTrayIcon.Warning
        if self._tray.isVisible():
            self._tray.showMessage(TITLE, text, icon, NOTIFICATION_MS)

    def _update_tray(self) -> None:
        lines = [TITLE]
        for host in self._hosts:
            if host in self._last_latency:
                latency = self._last_latency[host]
                lines.append(
                    f"{host}: {'lost' if latency is None else f'{latency:.0f} ms'}"
                )
        self._tray.setToolTip("\n".join(lines))
        alerting = any(self._alerts.is_alerting(h) for h in self._hosts)
        if alerting != self._tray_alerting:
            self._tray_alerting = alerting
            self._tray.setIcon(alert_icon() if alerting else app_icon())

    def _on_tray_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        if reason in (QSystemTrayIcon.Trigger, QSystemTrayIcon.DoubleClick):
            self.set_mode(Mode.NORMAL)

    # --- settings -----------------------------------------------------

    def _apply_params(self) -> None:
        """Apply TTL, timeout, size and interval on the fly."""
        self._ping_settings = self._controls.settings()
        self._monitor.update_settings(self._ping_settings)
        self._save_config()

    def _on_max_points_changed(self, max_points: int) -> None:
        self._max_points = max_points
        self._plot.set_max_points(max_points)
        self._save_config()

    def _on_alert_changed(self, alert_ms: int) -> None:
        self._alert_ms = alert_ms
        self._plot.set_alert_ms(alert_ms)
        self._save_config()

    def _on_notifications_changed(self, enabled: bool) -> None:
        self._notifications = enabled
        self._save_config()

    def _set_opacity(self, opacity: float) -> None:
        self._mini_opacity = opacity
        self._mini.set_opacity(opacity)
        self._save_config()

    def _on_mini_moved(self, pos) -> None:
        self._store.mini_pos = pos

    def _save_config(self) -> None:
        self._store.save(
            AppConfig(
                hosts=self._hosts,
                ping=self._ping_settings,
                max_points=self._max_points,
                alert_ms=self._alert_ms,
                notifications=self._notifications,
                mini_opacity=self._mini_opacity,
            )
        )

    # --- export -------------------------------------------------------

    def export_csv(self) -> None:
        """Ask for a file and write the measurement history to it as CSV."""
        if not len(self._history):
            QMessageBox.information(self, TITLE, "Nothing to export yet.")
            return
        path, _ = QFileDialog.getSaveFileName(
            self, "Export history", "ping_history.csv", "CSV files (*.csv)"
        )
        if not path:
            return
        try:
            with open(path, "w", newline="", encoding="utf-8") as file:
                self._history.write_csv(file)
        except OSError as exc:
            QMessageBox.warning(self, "Error", f"Cannot write the file:\n{exc}")

    def save_graph_image(self) -> None:
        """Ask for a file and save the graph to it as a PNG image."""
        path, _ = QFileDialog.getSaveFileName(
            self, "Save graph", "ping_graph.png", "PNG images (*.png)"
        )
        if path and not self._plot.grab().save(path, "PNG"):
            QMessageBox.warning(self, "Error", "Cannot write the file.")

    # --- window modes and dragging ------------------------------------

    def toggle_compact_mode(self) -> None:
        """Switch between normal and compact mode."""
        self.set_mode(Mode.NORMAL if self._mode is Mode.COMPACT else Mode.COMPACT)

    def set_mode(self, mode: Mode) -> None:
        """Switch the application to a display mode.

        Args:
            mode: Target mode; does nothing if it is already active, and the
                mini mode is refused when there is no system tray to control it.
        """
        if mode is self._mode:
            return
        if mode is Mode.MINI and not self._tray_available:
            return
        previous_pos = self._mini.pos() if self._mode is Mode.MINI else self.pos()
        self._mode = mode

        if mode is Mode.MINI:
            self._mini.move(self._store.mini_pos or self.pos())
            self.hide()
            self._mini.show()
            return

        self._move_action.setChecked(False)
        self._mini.hide()
        compact = mode is Mode.COMPACT
        # Hide or show the panels first: the window cannot be resized below the
        # minimum size of its visible content, so resizing before hiding would
        # leave the compact window far larger than COMPACT_SIZE.
        self.menuBar().setVisible(not compact)
        self._controls.setVisible(not compact)
        self._stats_panel.setVisible(not compact)
        self.layout().activate()
        if compact:
            self.setWindowFlags(Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
            self.resize(*COMPACT_SIZE)
            self.setWindowTitle(self._compact_title())
        else:
            self.setWindowFlags(Qt.Window)
            self.resize(*NORMAL_SIZE)
            self.setWindowTitle(TITLE)
        self.setWindowOpacity(COMPACT_OPACITY if compact else 1.0)
        self.move(previous_pos)
        self.show()
        self.activateWindow()

    def mousePressEvent(self, event) -> None:
        """Start dragging the window in compact mode."""
        if self._mode is Mode.COMPACT and event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPos() - self.pos()

    def mouseMoveEvent(self, event) -> None:
        """Drag the window in compact mode."""
        if self._mode is Mode.COMPACT and self._drag_offset is not None:
            self.move(event.globalPos() - self._drag_offset)

    def mouseReleaseEvent(self, event) -> None:
        """Finish dragging."""
        if event.button() == Qt.LeftButton:
            self._drag_offset = None

    def closeEvent(self, event) -> None:
        """Stop pinging, save the configuration and close the auxiliary windows."""
        self.stop_monitoring()
        self._save_config()
        self._mini.close()
        self._tray.hide()
        super().closeEvent(event)
