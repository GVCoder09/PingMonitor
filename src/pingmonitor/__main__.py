"""Entry point: ``python -m pingmonitor`` or the ``pingmonitor`` command."""

import sys

from PyQt5.QtWidgets import QApplication

from pingmonitor.resources import app_icon
from pingmonitor.ui.main_window import PingWindow

APP_ID = "io.github.gvcoder09.pingmonitor"


def _set_windows_app_id() -> None:
    """Give Windows a distinct app identity so the taskbar shows our icon.

    Without it, a run from source is grouped under the Python interpreter and
    gets its icon instead.
    """
    if sys.platform == "win32":
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)


def main() -> None:
    """Create the application, show the main window and run the event loop."""
    _set_windows_app_id()
    app = QApplication(sys.argv)
    app.setWindowIcon(app_icon())
    window = PingWindow()
    window.show()
    sys.exit(app.exec_())


if __name__ == "__main__":
    main()
