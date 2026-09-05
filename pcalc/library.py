"""
pcalc/library.py — Local library of user-imported add-ins and games.
These are files the user downloaded manually, stored locally on their machine.
No PGP verification — they are not from the official registry.
"""

import hashlib
import json
import os
import re
import shutil
import time
import unicodedata
from pathlib import Path

from platformdirs import user_data_dir

LIBRARY_DIR      = Path(user_data_dir("pancalc")) / "library"
LIBRARY_FILE     = LIBRARY_DIR / "library.json"
LIBRARY_FILES_DIR = LIBRARY_DIR / "files"

# Expected file extensions for validation
ADDIN_EXTS = {".g3a", ".g3e"}
GAME_EXTS  = {".rom", ".bin", ".gba", ".nes", ".sms", ".gg"}


def expected_extensions(item_type: str) -> set[str]:
    if item_type == "addin":
        return ADDIN_EXTS
    elif item_type == "game":
        return GAME_EXTS
    return set()


def has_valid_extension(path: str | Path, item_type: str | None = None) -> bool:
    """Check if a file path has an expected extension for the given type."""
    if item_type is None:
        return True
    exts = expected_extensions(item_type)
    if not exts:
        return True
    return Path(path).suffix.lower() in exts


def _sanitize(name: str) -> str:
    """Strip accents, replace spaces with _, remove special chars."""
    plain = unicodedata.normalize('NFD', name).encode('ascii', 'ignore').decode('ascii')
    plain = plain.replace(' ', '_')
    plain = re.sub(r'[^\w.\-]', '', plain)
    return plain


def _load() -> list[dict]:
    if not LIBRARY_FILE.exists():
        return []
    try:
        with open(LIBRARY_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def _save(items: list[dict]) -> None:
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)
    with open(LIBRARY_FILE, "w", encoding="utf-8") as f:
        json.dump(items, f, indent=2, ensure_ascii=False)


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _next_id(stem: str, existing: list[dict]) -> str:
    """Generate a unique ID from a filename stem, avoiding collisions."""
    stem_clean = _sanitize(stem).replace("_", "-").lower()
    base = stem_clean
    used = {e.get("id", "") for e in existing}
    suffix = 0
    while base in used:
        suffix += 1
        base = f"{stem_clean}-{suffix}"
    return base


def import_file(path: str, item_type: str = "addin",
                name: str | None = None, author: str | None = None,
                version: str | None = None,
                emulator: str | None = None,
                platform: str | None = None) -> dict:
    """
    Register a local file in the library.

    Args:
        path: Absolute or relative path to the local file.
        item_type: "addin" or "game".
        name: Display name (defaults to filename stem).
        author: Author name.
        version: Version string.
        emulator: Emulator name (games only).
        platform: Platform name (games only).

    Returns:
        The newly created library entry dict.

    Raises:
        FileNotFoundError: If the path does not exist.
        ValueError: If item_type is invalid.
    """
    src = Path(path).resolve()
    if not src.exists():
        raise FileNotFoundError(f"File not found: {src}")

    if item_type not in ("addin", "game"):
        raise ValueError(f"item_type must be 'addin' or 'game', got {item_type!r}")

    items = _load()

    item_id = _next_id(src.stem, items)
    name = name or _sanitize(src.stem)

    # Copy file into library files dir with a unique name
    LIBRARY_FILES_DIR.mkdir(parents=True, exist_ok=True)
    dest_name = f"{item_id}{src.suffix}"
    dest = LIBRARY_FILES_DIR / dest_name
    n = 1
    while dest.exists():
        dest = LIBRARY_FILES_DIR / f"{item_id}-{n}{src.suffix}"
        n += 1
    shutil.copy2(str(src), str(dest))

    entry = {
        "id":          item_id,
        "name":        name,
        "type":        item_type,
        "author":      author or "",
        "version":     version or "1.0",
        "local_path":  str(dest),
        "filename":    src.name,
        "sha256":      _sha256_file(dest),
        "imported_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }

    if item_type == "game":
        entry["emulator"] = emulator or "unknown"
        entry["platform"] = platform or "unknown"

    items.append(entry)
    _save(items)
    return entry


def remove(item_id: str) -> bool:
    """
    Remove an item from the local library by ID.
    Also deletes the physical file stored in the library.

    Args:
        item_id: The ID of the item to remove.

    Returns:
        True if removed, False if not found.
    """
    items = _load()
    entry = next((e for e in items if e.get("id") == item_id), None)
    if entry is None:
        return False
    items = [e for e in items if e.get("id") != item_id]
    _save(items)
    # Delete physical file if it lives inside the library
    local_path = entry.get("local_path", "")
    if local_path:
        p = Path(local_path)
        try:
            if p.exists() and str(p).startswith(str(LIBRARY_DIR)):
                p.unlink()
        except OSError:
            pass
    return True


def get_all(item_type: str | None = None) -> list[dict]:
    """
    Return all library items, optionally filtered by type.

    Args:
        item_type: "addin", "game", or None for all.

    Returns:
        List of item dicts.
    """
    items = _load()
    if item_type:
        return [e for e in items if e.get("type") == item_type]
    return items


def restore(entry: dict, data: bytes | None = None) -> bool:
    """
    Restore a previously removed library entry and its physical file.

    Used for trash undo. Re-creates the file at the entry's local_path and
    re-inserts the entry into library.json.

    Args:
        entry: The original library entry dict captured before removal.
        data: Bytes to write back to the physical file (or None to skip).

    Returns:
        True if the entry was restored, False if it already exists.
    """
    items = _load()
    if any(e.get("id") == entry.get("id") for e in items):
        return False
    local_path = entry.get("local_path", "")
    if local_path and data is not None:
        p = Path(local_path)
        try:
            p.parent.mkdir(parents=True, exist_ok=True)
            p.write_bytes(data)
        except OSError:
            pass
    items.insert(0, entry)
    _save(items)
    return True


def get(item_id: str) -> dict | None:
    """Return a single library item by ID, or None."""
    for e in _load():
        if e.get("id") == item_id:
            return e
    return None


def get_by_filename(filename: str) -> dict | None:
    """Return a library item matching the given filename (case-insensitive)."""
    fname_lower = filename.lower()
    for e in _load():
        if e.get("filename", "").lower() == fname_lower:
            return e
    return None
