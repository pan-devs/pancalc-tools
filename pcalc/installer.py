"""
pcalc/installer.py — Install, remove and track add-ins on a connected Casio Prizm.
Handles direct .g3a downloads and zip archives containing .g3a files.
"""

import hashlib
import io
import json
import shutil
import zipfile
from pathlib import Path

import requests
from platformdirs import user_cache_dir

from pcalc.calculator import Calculator


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INSTALLED_FILE = Path(user_cache_dir("pancalc")) / "installed.json"
CHUNK_SIZE     = 8192  # bytes per download chunk


# ---------------------------------------------------------------------------
# Installed registry (local state)
# ---------------------------------------------------------------------------

def _load_installed() -> dict:
    """Load the local installed add-ins database."""
    if not INSTALLED_FILE.exists():
        return {}
    try:
        with open(INSTALLED_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return {}


def _save_installed(data: dict) -> None:
    """Persist the installed add-ins database."""
    INSTALLED_FILE.parent.mkdir(parents=True, exist_ok=True)
    with open(INSTALLED_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def get_installed() -> dict:
    """
    Return the installed add-ins database.

    Returns:
        Dict mapping add-in ID → install metadata.
    """
    return _load_installed()


def is_installed(addin_id: str) -> bool:
    """Return True if the add-in is recorded as installed."""
    return addin_id in _load_installed()


# ---------------------------------------------------------------------------
# Download helpers
# ---------------------------------------------------------------------------

def _download_bytes(url: str, progress_callback=None) -> bytes:
    """
    Download a file from a URL and return its raw bytes.
    Optionally calls progress_callback(downloaded, total) per chunk.

    Raises:
        RuntimeError: On network or HTTP errors.
    """
    try:
        r = requests.get(url, stream=True, timeout=30)
        r.raise_for_status()
    except requests.exceptions.ConnectionError:
        raise RuntimeError("No internet connection.")
    except requests.exceptions.Timeout:
        raise RuntimeError("Download timed out.")
    except requests.exceptions.HTTPError as e:
        raise RuntimeError(f"HTTP error: {e}")

    total = int(r.headers.get("content-length", 0))
    downloaded = 0
    chunks = []

    for chunk in r.iter_content(chunk_size=CHUNK_SIZE):
        if chunk:
            chunks.append(chunk)
            downloaded += len(chunk)
            if progress_callback:
                progress_callback(downloaded, total)

    return b"".join(chunks)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _extract_g3a_from_zip(zip_bytes: bytes, zip_file: str) -> bytes:
    """
    Extract a specific .g3a file from a zip archive.

    Args:
        zip_bytes: Raw zip archive bytes.
        zip_file: Filename of the .g3a inside the zip.

    Returns:
        Raw bytes of the .g3a file.

    Raises:
        RuntimeError: If the file is not found in the archive.
    """
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        names = zf.namelist()
        # Try exact match first, then case-insensitive, then any .g3a
        target = None
        if zip_file in names:
            target = zip_file
        else:
            for name in names:
                if name.lower() == zip_file.lower():
                    target = name
                    break
        if target is None:
            # Last resort: grab the first .g3a in the archive
            for name in names:
                if name.lower().endswith(".g3a"):
                    target = name
                    break
        if target is None:
            raise RuntimeError(
                f"Could not find '{zip_file}' in the downloaded archive. "
                f"Contents: {', '.join(names)}"
            )
        return zf.read(target)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def install(addin: dict, calc: Calculator, progress_callback=None) -> Path:
    """
    Download and install an add-in to the connected calculator.

    Args:
        addin: Add-in dict from the registry.
        calc: Connected Calculator instance.
        progress_callback: Optional callable(downloaded, total) for progress.

    Returns:
        Path to the installed .g3a file on the calculator.

    Raises:
        RuntimeError: On download, extraction, or copy errors.
    """
    addin_id   = addin["id"]
    name       = addin.get("name", addin_id)
    dl_url     = addin["download_url"]
    dl_type    = addin.get("download_type", "direct")
    zip_file   = addin.get("zip_file", f"{addin_id}.g3a")
    g3a_name   = zip_file if dl_type == "zip" else Path(dl_url).name

    # Download
    raw = _download_bytes(dl_url, progress_callback=progress_callback)

    # Extract from zip if needed
    if dl_type == "zip":
        g3a_bytes = _extract_g3a_from_zip(raw, zip_file)
    else:
        g3a_bytes = raw

    # Copy to calculator root
    dest = calc.mount_path / g3a_name
    try:
        dest.write_bytes(g3a_bytes)
    except OSError as e:
        raise RuntimeError(f"Failed to write to calculator: {e}")

    # Record as installed
    installed = _load_installed()
    installed[addin_id] = {
        "id":         addin_id,
        "name":       name,
        "version":    addin.get("version", "unknown"),
        "filename":   g3a_name,
        "sha256":     _sha256(g3a_bytes),
        "mount_path": str(calc.mount_path),
    }
    _save_installed(installed)

    return dest


def remove(addin_id: str, calc: Calculator) -> None:
    """
    Remove an installed add-in from the calculator and the local database.

    Args:
        addin_id: ID of the add-in to remove.
        calc: Connected Calculator instance.

    Raises:
        RuntimeError: If the add-in is not installed or file cannot be deleted.
    """
    installed = _load_installed()
    if addin_id not in installed:
        raise RuntimeError(f"'{addin_id}' is not installed.")

    entry    = installed[addin_id]
    filename = entry.get("filename", f"{addin_id}.g3a")
    g3a_path = calc.mount_path / filename

    if g3a_path.exists():
        try:
            g3a_path.unlink()
        except OSError as e:
            raise RuntimeError(f"Failed to remove file from calculator: {e}")

    del installed[addin_id]
    _save_installed(installed)


def verify(addin_id: str, calc: Calculator) -> bool:
    """
    Verify that an installed add-in's SHA256 matches the recorded checksum.

    Args:
        addin_id: ID of the add-in to verify.
        calc: Connected Calculator instance.

    Returns:
        True if the checksum matches, False otherwise.

    Raises:
        RuntimeError: If the add-in is not installed or file is missing.
    """
    installed = _load_installed()
    if addin_id not in installed:
        raise RuntimeError(f"'{addin_id}' is not installed.")

    entry    = installed[addin_id]
    filename = entry.get("filename", f"{addin_id}.g3a")
    g3a_path = calc.mount_path / filename

    if not g3a_path.exists():
        raise RuntimeError(
            f"File '{filename}' not found on calculator. "
            f"It may have been deleted manually."
        )

    actual = _sha256(g3a_path.read_bytes())
    return actual == entry.get("sha256", "")