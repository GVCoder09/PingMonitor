"""Mini window: a tiny ping indicator."""

from typing import Optional

from PyQt5.QtCore import QPoint, QRectF, Qt, pyqtSignal
from PyQt5.QtGui import QColor, QFont, QPainter
from PyQt5.QtWidgets import QWidget

from pingmonitor.stats import PingStats

SIZE = (132, 42)
GOOD_MS = 50
OK_MS = 150
COLORS = {
    "good": QColor(80, 220, 100),
    "ok": QColor(240, 200, 60),
    "bad": QColor(240, 80, 80),
    "idle": QColor(200, 200, 200),
}


class MiniWindow(QWidget):
    """Tiny translucent ping indicator that mouse clicks pass through.

    The first line is the latest latency of the primary host, coloured by how
    good it is; the second line shows its average latency and packet loss.

    Normally the window receives no input at all, so it has to be controlled
    from the outside (the tray icon). In move mode (``set_movable``) it can be
    dragged with the mouse.

    Signals:
        moved(QPoint): The window was released at a new position.
    """

    moved = pyqtSignal(QPoint)

    def __init__(self) -> None:
        """Create the window in its click-through state."""
        super().__init__(
            None,
            Qt.FramelessWindowHint
            | Qt.WindowStaysOnTopHint
            | Qt.Tool
            | Qt.WindowTransparentForInput,
        )
        self.setAttribute(Qt.WA_TranslucentBackground)
        self.setAttribute(Qt.WA_ShowWithoutActivating)
        self.setFixedSize(*SIZE)
        self._headline = "—"
        self._details = ""
        self._color = COLORS["idle"]
        self._movable = False
        self._drag_offset = None
        self._opacity = 1.0

    @property
    def movable(self) -> bool:
        """Whether move mode is on."""
        return self._movable

    def set_movable(self, movable: bool) -> None:
        """Turn move mode on, or make the window click-through again.

        Args:
            movable: True to let the mouse drag the window.
        """
        self._movable = movable
        self._drag_offset = None
        # Changing a window flag hides the window, so show it again.
        self.setWindowFlag(Qt.WindowTransparentForInput, not movable)
        self.setCursor(Qt.SizeAllCursor if movable else Qt.ArrowCursor)
        self.setWindowOpacity(self._opacity)
        self.show()
        self.update()

    def set_opacity(self, opacity: float) -> None:
        """Set the opacity of the whole window.

        Args:
            opacity: From 0.1 (almost invisible) to 1.0 (fully opaque).
        """
        self._opacity = opacity
        self.setWindowOpacity(opacity)

    def show_state(
        self, latency: Optional[float], stats: PingStats, alerting: bool
    ) -> None:
        """Show the latest result and the running statistics.

        Args:
            latency: Latest latency in milliseconds, or None if lost.
            stats: Statistics of the same host.
            alerting: Whether the host is currently down or slow; forces red.
        """
        if latency is None:
            self._headline, self._color = "×", COLORS["bad"]
        else:
            self._headline = f"{latency:.0f} ms"
            if alerting or latency >= OK_MS:
                self._color = COLORS["bad"]
            elif latency >= GOOD_MS:
                self._color = COLORS["ok"]
            else:
                self._color = COLORS["good"]
        avg = f"avg {stats.avg:.0f} ms" if stats.received else "avg -"
        self._details = f"{avg} · {stats.loss_percent:.0f}% loss"
        self.update()

    def reset(self) -> None:
        """Return the indicator to its "no data" state."""
        self._headline, self._details = "—", ""
        self._color = COLORS["idle"]
        self.update()

    def mousePressEvent(self, event) -> None:
        """Start dragging in move mode."""
        if self._movable and event.button() == Qt.LeftButton:
            self._drag_offset = event.globalPos() - self.pos()

    def mouseMoveEvent(self, event) -> None:
        """Drag the window."""
        if self._drag_offset is not None:
            self.move(event.globalPos() - self._drag_offset)

    def mouseReleaseEvent(self, event) -> None:
        """Finish dragging and report the new position."""
        if self._drag_offset is not None and event.button() == Qt.LeftButton:
            self._drag_offset = None
            self.moved.emit(self.pos())

    def paintEvent(self, event) -> None:
        """Draw the translucent plate and the text with a shadow."""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.Antialiasing)
        rect = QRectF(self.rect())

        if self._movable:
            painter.setPen(QColor(90, 160, 255))
            painter.setBrush(QColor(0, 0, 0, 110))
            painter.drawRoundedRect(rect.adjusted(1, 1, -1, -1), 6, 6)
        else:
            painter.setPen(Qt.NoPen)
            painter.setBrush(QColor(0, 0, 0, 70))
            painter.drawRoundedRect(rect, 6, 6)

        top = QRectF(rect.left(), rect.top() + 3, rect.width(), rect.height() * 0.55)
        bottom = QRectF(
            rect.left(), top.bottom() - 2, rect.width(), rect.bottom() - top.bottom()
        )
        self._draw_text(painter, top, self._headline, 12, True, self._color)
        if self._details:
            self._draw_text(
                painter, bottom, self._details, 7, False, QColor(235, 235, 235)
            )

    def _draw_text(
        self,
        painter: QPainter,
        rect: QRectF,
        text: str,
        point_size: int,
        bold: bool,
        color: QColor,
    ) -> None:
        font = QFont(self.font())
        font.setBold(bold)
        font.setPointSize(point_size)
        painter.setFont(font)
        painter.setPen(QColor(0, 0, 0, 160))
        painter.drawText(rect.translated(1, 1), Qt.AlignCenter, text)
        painter.setPen(color)
        painter.drawText(rect, Qt.AlignCenter, text)
