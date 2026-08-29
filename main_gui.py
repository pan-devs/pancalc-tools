"""PanCalc Tools — GUI entry point (windowed mode)."""
import os
os.environ.setdefault("GDK_BACKEND", "x11")

# Tell flet_desktop to use the bundled client (avoids runtime download).
import sys
if getattr(sys, "frozen", False):
    _app_dir = os.path.dirname(sys.executable)
else:
    _app_dir = os.path.dirname(os.path.abspath(__file__))
_flet_client = os.path.join(_app_dir, "flet_client")
if os.path.isdir(_flet_client):
    os.environ.setdefault("FLET_CLIENT_STORAGE_DIR", _flet_client)

from pcalc.gui import main

if __name__ == "__main__":
    main()
