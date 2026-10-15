"""Panel that displays ping statistics, one row per host."""

from collections.abc import Iterable
from typing import Optional

from PyQt5.QtCore import Qt
from PyQt5.QtWidgets import QGridLayout, QLabel, QWidget

from pingmonitor.stats import PingStats
from pingmonitor.ui.colors import series_color

COLUMNS = (
    "Host",
    "Sent",
    "Received",
    "Loss",
    "Min",
    "Avg",
    "Max",
    "Jitter",
    "Median",
    "P95",
)


def format_ms(value: float, available: bool) -> str:
    """Format a latency for the table.

    Args:
        value: Latency in milliseconds.
        available: False if there is no data yet, which is shown as a dash.
    """
    return f"{value:.1f} ms" if available else "-"


class StatsPanel(QWidget):
    """Read-only table showing a ``PingStats`` snapshot per host."""

    def __init__(self, parent: Optional[QWidget] = None) -> None:
        """Create an empty panel.

        Args:
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self._layout = QGridLayout(self)
        self._layout.setHorizontalSpacing(14)
        self._cells: dict[str, list[QLabel]] = {}

    def set_hosts(self, hosts: Iterable[str]) -> None:
        """Rebuild the table for a new list of hosts, with empty values.

        Args:
            hosts: Hosts to show, in colour order.
        """
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        self._cells = {}

        for col, title in enumerate(COLUMNS):
            align = Qt.AlignLeft if col == 0 else Qt.AlignRight
            self._layout.addWidget(QLabel(f"<b>{title}</b>"), 0, col, align)

        for row, host in enumerate(hosts, start=1):
            cells = [QLabel() for _ in COLUMNS]
            color = series_color(row - 1).name()
            cells[0].setText(host)
            cells[0].setStyleSheet(f"color: {color}; font-weight: bold;")
            for col, cell in enumerate(cells):
                align = Qt.AlignLeft if col == 0 else Qt.AlignRight
                self._layout.addWidget(cell, row, col, align)
            self._cells[host] = cells
            self.show_stats(host, PingStats())

    def show_stats(self, host: str, stats: PingStats) -> None:
        """Display the current values of ``stats`` in the row of ``host``.

        Args:
            host: Host whose row to update; unknown hosts are ignored.
            stats: Statistics to show.
        """
        cells = self._cells.get(host)
        if cells is None:
            return
        got = stats.received > 0
        values = (
            str(stats.sent),
            str(stats.received),
            f"{stats.loss_percent:.1f}%",
            format_ms(stats.min, got),
            format_ms(stats.avg, got),
            format_ms(stats.max, got),
            format_ms(stats.jitter, got),
            format_ms(stats.median, got),
            format_ms(stats.p95, got),
        )
        for cell, text in zip(cells[1:], values):
            cell.setText(text)
