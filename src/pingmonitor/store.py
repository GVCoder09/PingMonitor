"""Persistence of the configuration between runs."""

from typing import Any, Optional

from PyQt5.QtCore import QPoint, QSettings

from pingmonitor.settings import (
    DEFAULT_HOST,
    AppConfig,
    PingSettings,
    parse_hosts,
)


class SettingsStore:
    """Reads and writes ``AppConfig`` and the mini window position."""

    def __init__(self, qsettings: Optional[QSettings] = None) -> None:
        """Create a store.

        Args:
            qsettings: Backend to use; defaults to the per-user application
                settings (registry on Windows, plist on macOS, INI on Linux).
        """
        self._q = qsettings or QSettings("PingMonitor", "PingMonitor")

    def load(self) -> AppConfig:
        """Return the saved configuration; missing or invalid values use defaults."""
        defaults = AppConfig()
        ping = PingSettings(
            ttl=self._get("ttl", defaults.ping.ttl, int),
            timeout=self._get("timeout", defaults.ping.timeout, int),
            size=self._get("size", defaults.ping.size, int),
            interval=self._get("interval", defaults.ping.interval, int),
        )
        hosts = parse_hosts(self._get("hosts", DEFAULT_HOST, str)) or defaults.hosts
        opacity = self._get("mini_opacity", defaults.mini_opacity, float)
        return AppConfig(
            hosts=hosts,
            ping=ping,
            max_points=max(1, self._get("max_points", defaults.max_points, int)),
            alert_ms=max(0, self._get("alert_ms", defaults.alert_ms, int)),
            mini_opacity=min(1.0, max(0.1, opacity)),
        )

    def save(self, config: AppConfig) -> None:
        """Save the configuration.

        Args:
            config: The configuration to remember.
        """
        self._q.setValue("hosts", ", ".join(config.hosts))
        self._q.setValue("ttl", config.ping.ttl)
        self._q.setValue("timeout", config.ping.timeout)
        self._q.setValue("size", config.ping.size)
        self._q.setValue("interval", config.ping.interval)
        self._q.setValue("max_points", config.max_points)
        self._q.setValue("alert_ms", config.alert_ms)
        self._q.setValue("mini_opacity", config.mini_opacity)
        self._q.sync()

    @property
    def mini_pos(self) -> Optional[QPoint]:
        """The remembered position of the mini window, or None."""
        pos = self._q.value("mini_pos")
        return pos if isinstance(pos, QPoint) else None

    @mini_pos.setter
    def mini_pos(self, pos: QPoint) -> None:
        self._q.setValue("mini_pos", pos)
        self._q.sync()

    def _get(self, key: str, default: Any, kind: type) -> Any:
        try:
            return self._q.value(key, default, type=kind)
        except (TypeError, ValueError):
            return default
