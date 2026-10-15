"""Panel with settings fields and control buttons."""

from typing import Optional

from PyQt5.QtCore import pyqtSignal
from PyQt5.QtGui import QIntValidator
from PyQt5.QtWidgets import (
    QGridLayout,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPushButton,
    QWidget,
)

from pingmonitor.settings import AppConfig, PingSettings, parse_hosts


class ControlsPanel(QWidget):
    """Input fields and buttons; it never pings anything itself.

    Signals:
        start_requested: The "Start" button was clicked.
        stop_requested: The "Stop" button was clicked.
        compact_requested: The "Compact mode" button was clicked.
        mini_requested: The "Mini" button was clicked.
        hosts_applied: The "Apply" button was clicked.
        params_changed: TTL, timeout, packet size or interval was edited.
        max_points_changed(int): The number of graph points was edited.
        alert_changed(int): The alert threshold was edited.
    """

    start_requested = pyqtSignal()
    stop_requested = pyqtSignal()
    compact_requested = pyqtSignal()
    mini_requested = pyqtSignal()
    hosts_applied = pyqtSignal()
    params_changed = pyqtSignal()
    max_points_changed = pyqtSignal(int)
    alert_changed = pyqtSignal(int)

    def __init__(self, config: AppConfig, parent: Optional[QWidget] = None) -> None:
        """Create the panel.

        Args:
            config: Initial values for the fields.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        ping = config.ping
        self.hosts_input = QLineEdit(", ".join(config.hosts))
        self.hosts_input.setPlaceholderText("host1, host2, ...")
        self.hosts_input.setToolTip("Comma-separated list of hosts to ping")
        self.ttl_input = self._number_input(ping.ttl)
        self.timeout_input = self._number_input(ping.timeout)
        self.size_input = self._number_input(ping.size)
        self.interval_input = self._number_input(ping.interval, 1, 3600)
        self.points_input = self._number_input(config.max_points)
        self.alert_input = self._number_input(config.alert_ms, 0, 10000)
        self.alert_input.setToolTip("Notify when latency exceeds this; 0 disables")

        self.apply_btn = QPushButton("Apply")
        self.start_btn = QPushButton("Start")
        self.stop_btn = QPushButton("Stop")
        self.compact_btn = QPushButton("Compact mode")
        self.mini_btn = QPushButton("Mini")

        self._busy = False
        self._running = False
        self._build_layout()
        self._connect_signals()
        self.set_running(False)

    def hosts(self) -> tuple[str, ...]:
        """Return the hosts currently typed into the field."""
        return parse_hosts(self.hosts_input.text())

    def set_hosts(self, hosts: tuple[str, ...]) -> None:
        """Replace the text of the hosts field.

        Args:
            hosts: Hosts to show.
        """
        self.hosts_input.setText(", ".join(hosts))

    def settings(self) -> PingSettings:
        """Return the ping parameters currently typed into the fields.

        Empty numeric fields fall back to the defaults of ``PingSettings``.
        """
        d = PingSettings()
        return PingSettings(
            ttl=self._int(self.ttl_input, d.ttl),
            timeout=self._int(self.timeout_input, d.timeout),
            size=self._int(self.size_input, d.size),
            interval=self._int(self.interval_input, d.interval),
        )

    def max_points(self) -> int:
        """Return the number of graph points; empty means the current default."""
        return self._int(self.points_input, AppConfig().max_points)

    def alert_ms(self) -> int:
        """Return the alert threshold in milliseconds (0 if empty or disabled)."""
        return self._int(self.alert_input, 0)

    def set_running(self, running: bool) -> None:
        """Enable or disable the "Start" and "Stop" buttons accordingly.

        Args:
            running: Whether monitoring is currently active.
        """
        self._running = running
        self._refresh_buttons()

    def set_busy(self, busy: bool) -> None:
        """Disable the host-related buttons while hosts are being checked.

        Args:
            busy: True while a reachability check is in progress.
        """
        self._busy = busy
        self._refresh_buttons()

    def _refresh_buttons(self) -> None:
        self.start_btn.setEnabled(not self._running and not self._busy)
        self.stop_btn.setEnabled(self._running)
        self.apply_btn.setEnabled(not self._busy)
        self.apply_btn.setText("Checking..." if self._busy else "Apply")

    def _number_input(self, value: int, low: int = 1, high: int = 1000) -> QLineEdit:
        """Create a narrow field that accepts integers from ``low`` to ``high``."""
        field = QLineEdit(str(value))
        field.setValidator(QIntValidator(low, high, self))
        field.setMaximumWidth(60)
        return field

    @staticmethod
    def _int(field: QLineEdit, default: int) -> int:
        text = field.text()
        return int(text) if text else default

    def _build_layout(self) -> None:
        layout = QGridLayout(self)
        layout.addWidget(QLabel("Hosts:"), 0, 0)
        layout.addWidget(self.hosts_input, 0, 1, 1, 2)
        layout.addWidget(self.apply_btn, 0, 3)

        layout.addWidget(self.start_btn, 1, 0)
        layout.addWidget(self.stop_btn, 1, 1)
        layout.addWidget(self.compact_btn, 1, 2)
        layout.addWidget(self.mini_btn, 1, 3)

        layout.addLayout(
            self._row(
                ("TTL:", self.ttl_input),
                ("Timeout (s):", self.timeout_input),
                ("Packet size:", self.size_input),
                ("Interval (s):", self.interval_input),
            ),
            2,
            0,
            1,
            4,
        )
        layout.addLayout(
            self._row(
                ("Graph points:", self.points_input),
                ("Alert above (ms):", self.alert_input),
            ),
            3,
            0,
            1,
            4,
        )

    @staticmethod
    def _row(*fields: tuple[str, QLineEdit]) -> QHBoxLayout:
        row = QHBoxLayout()
        for caption, field in fields:
            row.addWidget(QLabel(caption))
            row.addWidget(field)
        row.addStretch()
        return row

    def _connect_signals(self) -> None:
        self.start_btn.clicked.connect(self.start_requested)
        self.stop_btn.clicked.connect(self.stop_requested)
        self.compact_btn.clicked.connect(self.compact_requested)
        self.mini_btn.clicked.connect(self.mini_requested)
        self.apply_btn.clicked.connect(self.hosts_applied)

        for field in (
            self.ttl_input,
            self.timeout_input,
            self.size_input,
            self.interval_input,
        ):
            field.textChanged.connect(self._on_param_text_changed)
        self.points_input.textChanged.connect(self._on_points_text_changed)
        self.alert_input.textChanged.connect(self._on_alert_text_changed)

    def _on_param_text_changed(self, text: str) -> None:
        if text:
            self.params_changed.emit()

    def _on_points_text_changed(self, text: str) -> None:
        if text:
            self.max_points_changed.emit(int(text))

    def _on_alert_text_changed(self, text: str) -> None:
        self.alert_changed.emit(int(text) if text else 0)
