"""Colours that identify hosts consistently in the graph and the table."""

from PyQt5.QtGui import QColor

SERIES_COLORS = (
    "#ff0000",  # the first host keeps the classic red line
    "#1f77b4",
    "#ff7f0e",
    "#9467bd",
    "#17becf",
    "#8c564b",
    "#e377c2",
    "#7f7f7f",
)
MEAN_COLOR = QColor(0, 128, 0)
"""Colour of the dashed mean line of the first host (classic green)."""


def series_color(index: int) -> QColor:
    """Return the colour of the host at the given position.

    Args:
        index: Position of the host in the monitored list; wraps around.
    """
    return QColor(SERIES_COLORS[index % len(SERIES_COLORS)])
