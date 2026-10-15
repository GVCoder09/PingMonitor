"""PyInstaller entry point.

PyInstaller needs a plain script as its entry point; the real application lives
in the ``pingmonitor`` package.
"""

from pingmonitor.__main__ import main

if __name__ == "__main__":
    main()
