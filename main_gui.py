"""PanCalc Tools — GUI entry point (windowed mode)."""
import os
os.environ.setdefault("GDK_BACKEND", "x11")

from pcalc.gui import main

if __name__ == "__main__":
    main()
