# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/).

## [Unreleased]

### Added
- README with logo, badges and a FAQ.

## [0.1.0] - 2026-10-15

### Added
- Main window with a live latency graph, statistics table and settings.
- Monitoring of several hosts at once, each with its own colour, graph line and
  statistics row.
- Statistics: sent, received, loss, min, average, max, jitter, median and
  95th percentile.
- Alerts through tray notifications (host down, back up, latency above a
  threshold) and a red badge on the tray icon.
- Configurable ping interval, in addition to TTL, timeout and packet size.
- Settings are remembered between runs.
- Export of the measurement history to CSV and of the graph to a PNG image.
- Compact mode: frameless, always-on-top, translucent window.
- Mini mode: a tiny click-through indicator with latest latency, average and
  loss, controlled from the system tray; movable, with adjustable opacity.
- Application icon for the windows, the tray and the executables.
- Packaging: `pyproject.toml`, PyInstaller spec and a release workflow that
  builds standalone executables.

### Changed
- The graph is drawn with `QPainter` instead of matplotlib, which makes the
  application and its standalone builds much smaller and lighter.
- Host checks run in the background and stopping returns immediately, so the
  window no longer freezes.
- Lost packets are represented by `None` instead of a magic value of 0.
- The default host is `8.8.8.8`.

### Fixed
- An error raised while pinging (for example missing ICMP permissions) is now
  reported to the user instead of silently stopping the worker thread.
