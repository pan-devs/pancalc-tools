"""
PanCalc Tools — Package manager and developer toolkit for Casio Prizm calculators.
https://github.com/pan-devs/pancalc-tools
"""

__author__  = "Pan Devs"
__email__   = "pan.devs@proton.me"

__version__ = "1.0.0"

from pathlib import Path
from platformdirs import user_data_dir


def _data_root() -> Path:
    """Canonical base directory for convert/converted data (platform-agnostic)."""
    return Path(user_data_dir("pancalc"))


def _project_root() -> Path | None:
    """Find project root via pcalc package location (for migration)."""
    pkg = Path(__file__).resolve().parent
    candidate = pkg.parent
    if (candidate / "pyproject.toml").exists():
        return candidate
    return None