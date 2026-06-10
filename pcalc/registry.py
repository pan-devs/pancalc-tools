"""
pcalc/registry.py — Fetch, cache, and query the PanCalc add-in registry.
"""

import json
import os
import time
from pathlib import Path

import requests
from platformdirs import user_cache_dir

from pcalc import config

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

REGISTRY_URL = config.get("registry_url")
if REGISTRY_URL.endswith("registry.json"):
    ADDINS_BASE = REGISTRY_URL[:-len("registry.json")]
else:
    ADDINS_BASE = REGISTRY_URL.rsplit("/", 1)[0] + "/"

CACHE_DIR     = Path(user_cache_dir("pancalc"))
CACHE_FILE    = CACHE_DIR / "registry.json"
CACHE_FILE_GAMES = CACHE_DIR / "games.json"
CACHE_TTL     = 60 * 60 * 6  # 6 hours in seconds


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _cache_is_fresh() -> bool:
    """Return True if the cached registry exists and is less than TTL seconds old."""
    if not CACHE_FILE.exists():
        return False
    age = time.time() - CACHE_FILE.stat().st_mtime
    return age < CACHE_TTL


def _cache_games_is_fresh() -> bool:
    """Return True if the cached games registry exists and is less than TTL seconds old."""
    if not CACHE_FILE_GAMES.exists():
        return False
    age = time.time() - CACHE_FILE_GAMES.stat().st_mtime
    return age < CACHE_TTL


def _fetch_json(url: str) -> dict:
    """Download a JSON file from a URL and return it as a dict."""
    if url.startswith("file://"):
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        # Handle both file://localhost/path and file:///path
        path_str = parsed.path
        if os.name == 'nt' and path_str.startswith('/'):
            path_str = path_str[1:]
        p = Path(urllib.parse.unquote(path_str))
        with open(p, "r", encoding="utf-8") as f:
            return json.load(f)
    try:
        r = requests.get(url, timeout=10)
        r.raise_for_status()
        return r.json()
    except requests.exceptions.ConnectionError:
        raise RuntimeError("No internet connection. Try again later.")
    except requests.exceptions.Timeout:
        raise RuntimeError("Request timed out. Try again later.")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"HTTP error fetching registry: {e}")


def _load_addin(addin_path: str) -> dict:
    """Fetch a single add-in JSON from the registry repo."""
    url = ADDINS_BASE + addin_path
    return _fetch_json(url)


def _build_full_registry(index: dict) -> list[dict]:
    """
    Given the index (registry.json), fetch all individual add-in JSONs
    and return a flat list of add-in dicts.
    """
    addins = []
    for path in index.get("addins", []):
        try:
            addin = _load_addin(path)
            addins.append(addin)
        except RuntimeError:
            pass  # skip broken entries silently
    return addins


def _build_games_registry(index: dict) -> list[dict]:
    """
    Given the index (registry.json), fetch all individual game JSONs
    and return a flat list of game dicts.
    """
    games = []
    for path in index.get("games", []):
        try:
            game = _load_addin(path)
            games.append(game)
        except RuntimeError:
            pass  # skip broken entries silently
    return games


def _save_cache(addins: list[dict]) -> None:
    """Save the full add-in list to the local cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE, "w", encoding="utf-8") as f:
        json.dump(addins, f, indent=2, ensure_ascii=False)


def _load_cache() -> list[dict]:
    """Load the cached add-in list from disk."""
    with open(CACHE_FILE, "r", encoding="utf-8") as f:
        return json.load(f)


def _save_games_cache(games: list[dict]) -> None:
    """Save the full game list to the local cache."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    with open(CACHE_FILE_GAMES, "w", encoding="utf-8") as f:
        json.dump(games, f, indent=2, ensure_ascii=False)


def _load_games_cache() -> list[dict]:
    """Load the cached game list from disk."""
    with open(CACHE_FILE_GAMES, "r", encoding="utf-8") as f:
        return json.load(f)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def get_registry(force: bool = False) -> list[dict]:
    """
    Return the full list of add-in dicts from the registry.
    Uses cache if fresh, otherwise fetches from GitHub.

    Args:
        force: If True, bypass cache and always fetch fresh data.

    Returns:
        List of add-in dicts.

    Raises:
        RuntimeError: If network is unavailable and no cache exists.
    """
    if not force and _cache_is_fresh():
        return _load_cache()

    # Cache is stale or missing — fetch fresh
    index = _fetch_json(REGISTRY_URL)
    addins = _build_full_registry(index)
    _save_cache(addins)
    return addins


def get_addin(name: str, force: bool = False) -> dict | None:
    """
    Find a single add-in by ID or name (case-insensitive).

    Args:
        name: Add-in ID or display name to look up.
        force: Force registry refresh before searching.

    Returns:
        Add-in dict if found, None otherwise.
    """
    addins = get_registry(force=force)
    name_lower = name.lower()
    for addin in addins:
        if addin.get("id", "").lower() == name_lower:
            return addin
        if addin.get("name", "").lower() == name_lower:
            return addin
    return None


def search_registry(query: str) -> list[dict]:
    """
    Search add-ins by name, ID, description, or tags (case-insensitive).

    Args:
        query: Search string.

    Returns:
        List of matching add-in dicts.
    """
    addins = get_registry()
    q = query.lower()
    results = []
    for addin in addins:
        haystack = " ".join([
            addin.get("id", ""),
            addin.get("name", ""),
            addin.get("description", ""),
            addin.get("author", ""),
            " ".join(addin.get("tags", [])),
        ]).lower()
        if q in haystack:
            results.append(addin)
    return results


def filter_by_category(category: str) -> list[dict]:
    """
    Return all add-ins in a given category (case-insensitive).

    Args:
        category: Category string (e.g. "games", "math", "utilities").

    Returns:
        List of matching add-in dicts.
    """
    addins = get_registry()
    return [a for a in addins if a.get("category", "").lower() == category.lower()]


def get_games(force: bool = False) -> list[dict]:
    """
    Return the full list of game dicts from the registry.
    Uses cache if fresh, otherwise fetches from GitHub.

    Args:
        force: If True, bypass cache and always fetch fresh data.

    Returns:
        List of game dicts.

    Raises:
        RuntimeError: If network is unavailable and no cache exists.
    """
    if not force and _cache_games_is_fresh():
        return _load_games_cache()

    # Cache is stale or missing — fetch fresh
    index = _fetch_json(REGISTRY_URL)
    games = _build_games_registry(index)
    _save_games_cache(games)
    return games


def get_game(name: str, force: bool = False) -> dict | None:
    """
    Find a single game by ID or name (case-insensitive).

    Args:
        name: Game ID or display name to look up.
        force: Force registry refresh before searching.

    Returns:
        Game dict if found, None otherwise.
    """
    games = get_games(force=force)
    name_lower = name.lower()
    for game in games:
        if game.get("id", "").lower() == name_lower:
            return game
        if game.get("name", "").lower() == name_lower:
            return game
    return None


def search_games(query: str) -> list[dict]:
    """
    Search games by name, ID, description, emulator, platform or tags (case-insensitive).

    Args:
        query: Search string.

    Returns:
        List of matching game dicts.
    """
    games = get_games()
    q = query.lower()
    results = []
    for game in games:
        haystack = " ".join([
            game.get("id", ""),
            game.get("name", ""),
            game.get("description", ""),
            game.get("author", ""),
            game.get("emulator", ""),
            game.get("platform", ""),
            " ".join(game.get("tags", [])),
        ]).lower()
        if q in haystack:
            results.append(game)
    return results


def invalidate_cache() -> None:
    """Delete the local registry cache, forcing a fresh fetch on next call."""
    if CACHE_FILE.exists():
        CACHE_FILE.unlink()
    if CACHE_FILE_GAMES.exists():
        CACHE_FILE_GAMES.unlink()