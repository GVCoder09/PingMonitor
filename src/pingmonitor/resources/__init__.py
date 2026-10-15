"""Bundled static resources (the application icon)."""

from pathlib import Path

from PyQt5.QtGui import QColor, QIcon, QPainter, QPixmap

RESOURCES_DIR = Path(__file__).resolve().parent
ICON_PATH = RESOURCES_DIR / "icon.png"
"""Works from source and from a PyInstaller bundle, as long as this directory is
shipped next to the module (see ``packaging/pingmonitor.spec``)."""


def app_icon() -> QIcon:
    """Return the application icon."""
    return QIcon(str(ICON_PATH))


def alert_icon() -> QIcon:
    """Return the application icon with a red badge in the corner."""
    pixmap = QPixmap(str(ICON_PATH))
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.Antialiasing)
    badge = pixmap.width() * 0.42
    x = pixmap.width() - badge
    painter.setPen(QColor("white"))
    painter.setBrush(QColor(230, 60, 60))
    painter.drawEllipse(int(x), 0, int(badge), int(badge))
    painter.end()
    return QIcon(pixmap)


__all__ = ["ICON_PATH", "RESOURCES_DIR", "alert_icon", "app_icon"]
