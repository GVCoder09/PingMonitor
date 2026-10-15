# Contributing

Thanks for your interest in PingMonitor! Bug reports and pull requests are
welcome.

## Development setup

```bash
git clone https://github.com/GVCoder09/PingMonitor.git
cd PingMonitor
python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
```

## Before opening a pull request

```bash
ruff format .
ruff check .
pytest
```

The UI tests run on Qt's `offscreen` platform (set automatically in
`tests/conftest.py`), so no display is needed. They use `pytest-qt` with the
PyQt5 binding (`qt_api = "pyqt5"` in `pyproject.toml`), even if other Qt
bindings are installed.

## Guidelines

- All code, comments, documentation, interface text and commit messages are
  written in **English**.
- Docstrings follow [PEP 257](https://peps.python.org/pep-0257/) and the
  [Google style](https://google.github.io/styleguide/pyguide.html#38-comments-and-docstrings)
  (`Args:`, `Returns:`, ...). `ruff` enforces this.
- Keep the logic (`stats`, `settings`, `monitor`) independent of the widgets in
  `pingmonitor/ui`, and cover new logic with tests.

## Building a standalone executable

```bash
pip install -e ".[build]"
pyinstaller packaging/pingmonitor.spec --noconfirm
```

The result is written to `dist/`. Always build in a clean virtual environment:
PyInstaller bundles whatever it finds importable.
