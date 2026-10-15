"""In-memory log of every measurement, with CSV export."""

import csv
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Optional, TextIO

MAX_SAMPLES = 100_000
"""Default capacity of the log; the oldest samples are dropped beyond it."""


@dataclass(frozen=True)
class Sample:
    """One measurement.

    Attributes:
        timestamp: When the reply (or the timeout) was observed.
        host: The pinged host.
        latency: Round-trip time in milliseconds, or None for a lost packet.
    """

    timestamp: datetime
    host: str
    latency: Optional[float]


class HistoryLog:
    """Bounded chronological log of measurements."""

    def __init__(self, max_samples: int = MAX_SAMPLES) -> None:
        """Create an empty log.

        Args:
            max_samples: Capacity; the oldest samples are discarded first.
        """
        self._samples: deque[Sample] = deque(maxlen=max_samples)

    def __len__(self) -> int:
        """Return the number of stored samples."""
        return len(self._samples)

    def record(
        self, host: str, latency: Optional[float], timestamp: Optional[datetime] = None
    ) -> None:
        """Append a measurement.

        Args:
            host: The pinged host.
            latency: Round-trip time in milliseconds, or None if lost.
            timestamp: Observation time; defaults to now (local time zone).
        """
        when = timestamp or datetime.now().astimezone()
        self._samples.append(Sample(when, host, latency))

    def clear(self) -> None:
        """Remove all samples."""
        self._samples.clear()

    def write_csv(self, file: TextIO) -> None:
        """Write the log as CSV.

        The columns are ``timestamp`` (ISO 8601), ``host``, ``latency_ms``
        (empty for lost packets) and ``status`` (``ok`` or ``lost``).

        Args:
            file: A text file opened with ``newline=""``.
        """
        writer = csv.writer(file)
        writer.writerow(["timestamp", "host", "latency_ms", "status"])
        for sample in self._samples:
            lost = sample.latency is None
            writer.writerow(
                [
                    sample.timestamp.isoformat(timespec="milliseconds"),
                    sample.host,
                    "" if lost else f"{sample.latency:.3f}",
                    "lost" if lost else "ok",
                ]
            )
