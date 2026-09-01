"""
pcalc/config.py — Local configuration for PanCalc Tools.
Stores user preferences in a platform-appropriate directory.
"""

import json
from pathlib import Path
from platformdirs import user_config_dir

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

CONFIG_DIR  = Path(user_config_dir("pancalc"))
CONFIG_FILE = CONFIG_DIR / "config.json"

DEFAULTS = {
    "registry_url":   "https://raw.githubusercontent.com/pan-devs/pancalc-registry/main/registry.json",
    "cache_ttl_hours": 6,
    "auto_update":     True,   # check for registry updates on launch
    "check_updates":   True,   # check GitHub Releases for a new app version on launch
    "confirm_install": True,   # ask before installing
    "confirm_remove":  True,   # ask before removing
    "confirm_push":    True,   # ask before pushing converted files (on by default, like dark mode)
    "theme_mode":      "dark", # default to dark mode
}


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _load_raw() -> dict:
    """Load raw config from disk, return empty dict if missing or corrupt."""
    if not CONFIG_FILE.exists():
        return {}
    try:
        with open(CONFIG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_raw(data: dict) -> None:
    """Save raw config dict to disk."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get(key: str):
    """
    Get a config value by key.
    Falls back to DEFAULTS if the key is not set by the user.

    Args:
        key: Config key name.

    Returns:
        The config value, or None if key doesn't exist in defaults either.
    """
    raw = _load_raw()
    return raw.get(key, DEFAULTS.get(key))


def set(key: str, value) -> None:
    """
    Set a config value and persist it to disk.

    Args:
        key: Config key name.
        value: Value to store.
    """
    raw = _load_raw()
    raw[key] = value
    _save_raw(raw)


def get_all() -> dict:
    """
    Return the full config, merging user overrides over defaults.

    Returns:
        Dict with all config keys and their effective values.
    """
    raw = _load_raw()
    return {**DEFAULTS, **raw}


def reset(key: str | None = None) -> None:
    """
    Reset a specific key (or all config) to defaults.

    Args:
        key: Key to reset. If None, resets everything.
    """
    if key is None:
        _save_raw({})
    else:
        raw = _load_raw()
        raw.pop(key, None)
        _save_raw(raw)


def config_path() -> Path:
    """Return the path to the config file (useful for --help or debug output)."""
    return CONFIG_FILE