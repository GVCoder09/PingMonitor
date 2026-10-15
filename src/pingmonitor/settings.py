"""Application configuration: ping parameters, display options and defaults."""

import re
from dataclasses import dataclass, field

DEFAULT_HOST = "8.8.8.8"
DEFAULT_MAX_POINTS = 15
"""Number of measurements shown on the graph by default."""
MAX_HOSTS = 8
"""Largest number of hosts that can be monitored at the same time."""


@dataclass(frozen=True)
class PingSettings:
    """Parameters shared by all ICMP echo requests.

    Attributes:
        ttl: IP time-to-live of the outgoing packet.
        timeout: Seconds to wait for a reply before counting the packet as lost.
        size: Payload size in bytes.
        interval: Seconds between two consecutive pings of the same host.
    """

    ttl: int = 56
    timeout: int = 3
    size: int = 32
    interval: int = 1


@dataclass(frozen=True)
class AppConfig:
    """Everything that is remembered between runs.

    Attributes:
        hosts: Hosts to monitor.
        ping: Ping parameters.
        max_points: Number of measurements shown on the graph.
        alert_ms: Latency in milliseconds above which an alert is raised;
            0 disables the latency alert.
        notifications: Whether alerts are shown as tray notifications. The
            tray icon badge is shown regardless.
        mini_opacity: Opacity of the mini window, from 0.1 to 1.0.
    """

    hosts: tuple[str, ...] = (DEFAULT_HOST,)
    ping: PingSettings = field(default_factory=PingSettings)
    max_points: int = DEFAULT_MAX_POINTS
    alert_ms: int = 0
    notifications: bool = True
    mini_opacity: float = 1.0


def parse_hosts(text: str) -> tuple[str, ...]:
    """Split user input into a list of unique hosts.

    Hosts may be separated by commas, semicolons or whitespace. The order is
    preserved and the list is truncated to ``MAX_HOSTS`` entries.

    Args:
        text: Raw text from the host field.

    Returns:
        The hosts, without duplicates; empty if the text has none.
    """
    hosts = dict.fromkeys(h for h in re.split(r"[\s,;]+", text) if h)
    return tuple(hosts)[:MAX_HOSTS]
