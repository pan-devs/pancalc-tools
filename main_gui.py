"""PanCalc Tools — GUI entry point (windowed mode)."""
import os
import sys

os.environ.setdefault("GDK_BACKEND", "x11")

# Point flet_desktop at the bundled client (avoids runtime download / SSL).
# flet_desktop resolves the client via FLET_VIEW_PATH, expecting flet.exe
# directly inside the given directory.
if getattr(sys, "frozen", False):
    _app_dir = os.path.dirname(sys.executable)
else:
    _app_dir = os.path.dirname(os.path.abspath(__file__))
_flet_bin = os.path.join(_app_dir, "flet_client", "flet")
if os.path.isfile(os.path.join(_flet_bin, "flet.exe")):
    os.environ["FLET_VIEW_PATH"] = _flet_bin

from pcalc.gui import main

if __name__ == "__main__":
    main()
