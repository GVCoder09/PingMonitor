"""Running statistics of ping results."""

import math
from collections import deque
from collections.abc import Sequence
from typing import Optional

PERCENTILE_WINDOW = 1000
"""Number of most recent replies used for the median and percentiles."""


def percentile(sorted_values: Sequence[float], q: float) -> float:
    """Return a percentile using linear interpolation.

    Args:
        sorted_values: Values in ascending order.
        q: Percentile from 0 to 100.

    Returns:
        The percentile, or 0 if there are no values.
    """
    if not sorted_values:
        return 0.0
    position = (len(sorted_values) - 1) * q / 100
    low = math.floor(position)
    high = min(low + 1, len(sorted_values) - 1)
    return sorted_values[low] + (sorted_values[high] - sorted_values[low]) * (
        position - low
    )


class PingStats:
    """Accumulates counters, latency extremes, jitter and percentiles.

    Attributes:
        sent: Number of packets sent.
        received: Number of replies received.
        min: Smallest latency in milliseconds (``inf`` until a reply arrives).
        max: Largest latency in milliseconds.
    """

    def __init__(self) -> None:
        """Create empty statistics."""
        self.reset()

    def reset(self) -> None:
        """Reset all counters to their initial state."""
        self.sent = 0
        self.received = 0
        self.min = float("inf")
        self.max = 0.0
        self._total = 0.0
        self._window: deque[float] = deque(maxlen=PERCENTILE_WINDOW)
        self._previous: Optional[float] = None
        self._jitter_total = 0.0
        self._jitter_count = 0

    def record(self, latency: Optional[float]) -> None:
        """Record one ping result.

        Args:
            latency: Round-trip time in milliseconds, or None if the packet
                got no reply.
        """
        self.sent += 1
        if latency is None:
            return
        self.received += 1
        self._total += latency
        self.min = min(self.min, latency)
        self.max = max(self.max, latency)
        self._window.append(latency)
        if self._previous is not None:
            self._jitter_total += abs(latency - self._previous)
            self._jitter_count += 1
        self._previous = latency

    @property
    def avg(self) -> float:
        """Average latency over received replies, or 0 if there are none."""
        return self._total / self.received if self.received else 0.0

    @property
    def loss_percent(self) -> float:
        """Share of lost packets, in percent."""
        return (self.sent - self.received) / self.sent * 100 if self.sent else 0.0

    @property
    def jitter(self) -> float:
        """Mean absolute difference between consecutive replies, in milliseconds."""
        return self._jitter_total / self._jitter_count if self._jitter_count else 0.0

    @property
    def median(self) -> float:
        """Median latency over the most recent replies."""
        return percentile(sorted(self._window), 50)

    @property
    def p95(self) -> float:
        """95th percentile latency over the most recent replies."""
        return percentile(sorted(self._window), 95)
