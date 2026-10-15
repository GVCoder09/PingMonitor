import pytest
from PyQt5.QtCore import QPoint, QSettings

from pingmonitor.settings import AppConfig, PingSettings
from pingmonitor.store import SettingsStore


@pytest.fixture
def store(tmp_path):
    ini = QSettings(str(tmp_path / "settings.ini"), QSettings.IniFormat)
    return SettingsStore(ini)


def test_defaults_when_nothing_is_saved(store):
    assert store.load() == AppConfig()
    assert store.mini_pos is None


def test_roundtrip(store):
    config = AppConfig(
        hosts=("a.test", "b.test"),
        ping=PingSettings(ttl=10, timeout=2, size=64, interval=5),
        max_points=40,
        alert_ms=120,
        mini_opacity=0.5,
    )
    store.save(config)
    assert store.load() == config


def test_invalid_values_fall_back_to_defaults(store):
    store._q.setValue("ttl", "not a number")
    store._q.setValue("hosts", " , ")
    assert store.load().ping.ttl == PingSettings().ttl
    assert store.load().hosts == AppConfig().hosts


def test_values_are_clamped(store):
    store._q.setValue("mini_opacity", 7)
    store._q.setValue("max_points", -3)
    config = store.load()
    assert config.mini_opacity == 1.0
    assert config.max_points == 1


def test_mini_position_roundtrip(store):
    store.mini_pos = QPoint(12, 34)
    assert store.mini_pos == QPoint(12, 34)
