"""Latency graph drawn directly with ``QPainter``."""

import math
from collections import deque
from collections.abc import Iterable
from typing import Optional

from PyQt5.QtCore import QPointF, QRectF, Qt
from PyQt5.QtGui import QColor, QPainter, QPainterPath, QPalette, QPen
from PyQt5.QtWidgets import QWidget

from pingmonitor.ui.colors import MEAN_COLOR, series_color

MIN_Y_MAX = 20
"""Smallest upper bound of the Y axis, in milliseconds."""
EMPTY_Y_MAX = 100
"""Upper bound of the Y axis while there is no data."""
LOSS_COLOR = QColor(255, 0, 0)
ALERT_COLOR = QColor(235, 140, 20)
MARGIN_LEFT, MARGIN_RIGHT, MARGIN_TOP, MARGIN_BOTTOM = 46, 14, 10, 24


def nice_step(span: float, target_ticks: int = 5) -> float:
    """Return a round tick step (1, 2 or 5 times a power of ten).

    Args:
        span: Length of the axis in data units; must be positive.
        target_ticks: Approximate number of ticks wanted.
    """
    raw = span / target_ticks
    magnitude = 10 ** math.floor(math.log10(raw))
    for factor in (1, 2, 5, 10):
        if raw <= factor * magnitude:
            return factor * magnitude
    return 10 * magnitude


class PingPlot(QWidget):
    """Graph of the last N measurements of one or more hosts.

    Every host is a coloured line with a dashed mean line; lost packets are red
    dashed vertical lines; the alert threshold, if set, is an orange line.
    """

    def __init__(self, max_points: int, parent: Optional[QWidget] = None) -> None:
        """Create an empty graph.

        Args:
            max_points: Number of measurements to keep and show per host.
            parent: Optional parent widget.
        """
        super().__init__(parent)
        self.setMinimumSize(260, 150)
        self._max_points = max_points
        self._alert_ms = 0
        self._series: dict[str, deque[Optional[float]]] = {}

    def set_hosts(self, hosts: Iterable[str]) -> None:
        """Replace the displayed hosts with new, empty series.

        Args:
            hosts: Hosts to draw, in colour order.
        """
        self._series = {h: deque(maxlen=self._max_points) for h in hosts}
        self.update()

    def add(self, host: str, latency: Optional[float]) -> None:
        """Append a measurement; unknown hosts are ignored.

        Args:
            host: The pinged host.
            latency: Latency in milliseconds, or None if the packet was lost.
        """
        series = self._series.get(host)
        if series is not None:
            series.append(latency)
            self.update()

    def clear(self) -> None:
        """Remove all measurements but keep the hosts."""
        for series in self._series.values():
            series.clear()
        self.update()

    def set_max_points(self, max_points: int) -> None:
        """Change the number of visible points, keeping the newest ones.

        Args:
            max_points: New number of measurements to keep per host.
        """
        self._max_points = max_points
        self._series = {
            host: deque(series, maxlen=max_points)
            for host, series in self._series.items()
        }
        self.update()

    def set_alert_ms(self, alert_ms: int) -> None:
        """Set the alert threshold line.

        Args:
            alert_ms: Threshold in milliseconds; 0 hides the line.
        """
        self._alert_ms = alert_ms
        self.update()

    def _y_max(self) -> float:
        values = [v for s in self._series.values() for v in s if v is not None]
        if not values:
            return EMPTY_Y_MAX
        top = max(max(values) * 1.2, MIN_Y_MAX)
        if self._alert_ms:
            top = max(top, self._alert_ms * 1.1)
        return top

    def paintEvent(self, event) -> None:
        """Draw the grid, the series and the legend."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        palette = self.palette()
        painter.fillRect(self.rect(), palette.base())

        plot = QRectF(
            MARGIN_LEFT,
            MARGIN_TOP,
            self.width() - MARGIN_LEFT - MARGIN_RIGHT,
            self.height() - MARGIN_TOP - MARGIN_BOTTOM,
        )
        if plot.width() < 10 or plot.height() < 10:
            return

        y_max = self._y_max()
        self._draw_grid(painter, plot, y_max)
        self._draw_losses(painter, plot)
        if self._alert_ms:
            self._draw_alert_line(painter, plot, y_max)
        for index, (_host, series) in enumerate(self._series.items()):
            mean = MEAN_COLOR if index == 0 else series_color(index)
            self._draw_series(painter, plot, y_max, series, series_color(index), mean)
        self._draw_legend(painter, plot)

    def _x(self, plot: QRectF, i: int) -> float:
        if self._max_points <= 1:
            return plot.center().x()
        return plot.left() + i / (self._max_points - 1) * plot.width()

    @staticmethod
    def _y(plot: QRectF, y_max: float, value: float) -> float:
        return plot.bottom() - min(value, y_max) / y_max * plot.height()

    def _draw_grid(self, painter: QPainter, plot: QRectF, y_max: float) -> None:
        palette = self.palette()
        grid = QColor(palette.color(QPalette.Mid))
        text = palette.color(QPalette.Text)
        step = nice_step(y_max)
        painter.setFont(self.font())
        tick = 0.0
        while tick <= y_max:
            y = self._y(plot, y_max, tick)
            painter.setPen(QPen(grid, 1))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))
            painter.setPen(text)
            label_rect = QRectF(0, y - 8, MARGIN_LEFT - 6, 16)
            painter.drawText(label_rect, Qt.AlignRight | Qt.AlignVCenter, f"{tick:g}")
            tick += step
        painter.setPen(QPen(grid, 1))
        painter.drawRect(plot)
        painter.setPen(text)
        painter.drawText(
            QRectF(plot.left(), plot.bottom() + 4, plot.width(), 18),
            Qt.AlignCenter,
            f"ms • last {self._max_points} measurements",
        )

    def _draw_losses(self, painter: QPainter, plot: QRectF) -> None:
        pen = QPen(LOSS_COLOR, 3, Qt.DashLine)
        painter.setPen(pen)
        for series in self._series.values():
            for i, value in enumerate(series):
                if value is None:
                    x = self._x(plot, i)
                    painter.drawLine(QPointF(x, plot.top()), QPointF(x, plot.bottom()))

    def _draw_alert_line(self, painter: QPainter, plot: QRectF, y_max: float) -> None:
        y = self._y(plot, y_max, self._alert_ms)
        painter.setPen(QPen(ALERT_COLOR, 1.5, Qt.DashDotLine))
        painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))

    def _draw_series(
        self,
        painter: QPainter,
        plot: QRectF,
        y_max: float,
        series: deque,
        color: QColor,
        mean_color: QColor,
    ) -> None:
        path = QPainterPath()
        drawing = False
        isolated = []
        values = list(series)
        for i, value in enumerate(values):
            if value is None:
                drawing = False
                continue
            point = QPointF(self._x(plot, i), self._y(plot, y_max, value))
            before = i > 0 and values[i - 1] is not None
            after = i + 1 < len(values) and values[i + 1] is not None
            if not before and not after:
                isolated.append(point)  # a lone point would be invisible
            if drawing:
                path.lineTo(point)
            else:
                path.moveTo(point)
                drawing = True
        painter.setPen(QPen(color, 1.5))
        painter.setBrush(Qt.NoBrush)
        painter.drawPath(path)
        painter.setBrush(color)
        for point in isolated:
            painter.drawEllipse(point, 2.5, 2.5)

        valid = [v for v in series if v is not None]
        if valid:
            y = self._y(plot, y_max, sum(valid) / len(valid))
            painter.setPen(QPen(mean_color, 2, Qt.DashLine))
            painter.drawLine(QPointF(plot.left(), y), QPointF(plot.right(), y))

    def _draw_legend(self, painter: QPainter, plot: QRectF) -> None:
        if not self._series:
            return
        metrics = painter.fontMetrics()
        row_height = metrics.height() + 2
        rows = []
        for index, (host, series) in enumerate(self._series.items()):
            valid = [v for v in series if v is not None]
            avg = f"avg {sum(valid) / len(valid):.1f} ms" if valid else "no data"
            rows.append((series_color(index), f"{host}  {avg}"))
        width = max(metrics.horizontalAdvance(text) for _, text in rows) + 30
        box = QRectF(plot.left() + 6, plot.top() + 6, width, row_height * len(rows) + 6)
        background = QColor(self.palette().color(QPalette.Base))
        background.setAlpha(220)
        painter.setPen(Qt.NoPen)
        painter.setBrush(background)
        painter.drawRoundedRect(box, 4, 4)
        for i, (color, text) in enumerate(rows):
            top = box.top() + 3 + i * row_height
            painter.setBrush(color)
            painter.drawRect(QRectF(box.left() + 6, top + 4, 12, metrics.height() - 6))
            painter.setPen(self.palette().color(QPalette.Text))
            painter.drawText(
                QRectF(box.left() + 24, top, width, row_height),
                Qt.AlignLeft | Qt.AlignVCenter,
                text,
            )
            painter.setPen(Qt.NoPen)
