import os
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


def _get_addin_files(addin: dict) -> list[dict]:
    """Resolve the list of files to install from an add-in dict."""
    if "files" in addin:
        return addin["files"]

    addin_id = addin["id"]
    dl_url   = addin["download_url"]
    dl_type  = addin.get("download_type", "direct")
    zip_file = addin.get("zip_file", f"{addin_id}.g3a")

    return [{
        "download_url": dl_url,
        "download_type": dl_type,
        "zip_file": zip_file,
    }]


def _resolve_file_name(file_info: dict, addin_id: str) -> str:
    """Determine the output file name for a file info entry."""
    if "filename" in file_info:
        return file_info["filename"]
    if file_info.get("download_type") == "zip":
        return file_info.get("zip_file", f"{addin_id}.g3a")
    return Path(file_info["download_url"]).name


def _write_with_progress(dest: Path, data: bytes, filename: str, write_callback=None) -> None:
    """Write bytes to a file in chunks, reporting progress via write_callback(filename, current, total)."""
    chunk_size = 8192
    total = len(data)
    written = 0
    if write_callback:
        write_callback(filename, 0, total)
    try:
        with open(dest, 'wb') as f:
            while written < total:
                chunk = data[written:written + chunk_size]
                f.write(chunk)
                written += len(chunk)
                if write_callback:
                    write_callback(filename, written, total)
            f.flush()
            try:
                os.fsync(f.fileno())
            except OSError:
                pass
    except OSError as e:
        raise RuntimeError(f"Failed to write '{filename}' to calculator: {e}")


def install(addin: dict, calc: Calculator, progress_callback=None, write_callback=None) -> list[Path]:
    """
    Download and install one or more add-in files to the connected calculator.

    Args:
        addin: Add-in dict from the registry.
        calc: Connected Calculator instance.
        progress_callback: Optional callable(downloaded, total) for download progress.
        write_callback: Optional callable(filename, written, total) for write progress.

    Returns:
        List of Paths to the installed files on the calculator.

    Raises:
        RuntimeError: On download, extraction, or copy errors.
    """
    addin_id = addin["id"]
    name     = addin.get("name", addin_id)

    files_info = _get_addin_files(addin)
    installed_paths = []
    file_records = []

    for i, file_info in enumerate(files_info):
        dl_url  = file_info["download_url"]
        dl_type = file_info.get("download_type", "direct")
        zip_file = file_info.get("zip_file", f"{addin_id}.g3a")
        filename = _resolve_file_name(file_info, addin_id)

        # Download
        raw = _download_bytes(dl_url, progress_callback=progress_callback)

        # Extract from zip if needed
        if dl_type == "zip":
            g3a_bytes = _extract_g3a_from_zip(raw, zip_file)
        else:
            g3a_bytes = raw

        # Check write access
        if not os.access(calc.mount_path, os.W_OK):
            raise RuntimeError(
                f"Calculator at '{calc.mount_path}' is mounted read-only. "
                f"Safely eject and reconnect, then try again."
            )

        # Write to calculator with progress
        dest = calc.mount_path / filename
        _write_with_progress(dest, g3a_bytes, filename, write_callback=write_callback)
        installed_paths.append(dest)
        file_records.append({"filename": filename, "sha256": _sha256(g3a_bytes)})

    # Record as installed
    installed = _load_installed()
    installed[addin_id] = {
        "id":         addin_id,
        "name":       name,
        "version":    addin.get("version", "unknown"),
        "files":      file_records,
        "mount_path": str(calc.mount_path),
    }
    _save_installed(installed)

    return installed_paths


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

    entry = installed[addin_id]

    # Resolve files to remove (supports both multi-file and legacy single-file)
    files_to_remove = []
    if "files" in entry:
        files_to_remove = [f["filename"] for f in entry["files"]]
    elif "filename" in entry:
        files_to_remove = [entry["filename"]]

    for filename in files_to_remove:
        path = calc.mount_path / filename
        if path.exists():
            try:
                path.unlink()
            except OSError as e:
                raise RuntimeError(f"Failed to remove '{filename}' from calculator: {e}")

    del installed[addin_id]
    _save_installed(installed)


def verify(addin_id: str, calc: Calculator) -> bool:
    """
    Verify that an installed add-in's SHA256 matches the recorded checksum.

    Args:
        addin_id: ID of the add-in to verify.
        calc: Connected Calculator instance.

    Returns:
        True if all checksums match, False otherwise.

    Raises:
        RuntimeError: If the add-in is not installed or any file is missing.
    """
    installed = _load_installed()
    if addin_id not in installed:
        raise RuntimeError(f"'{addin_id}' is not installed.")

    entry = installed[addin_id]

    # Resolve files to verify (supports both multi-file and legacy single-file)
    files_to_verify = []
    if "files" in entry:
        files_to_verify = entry["files"]
    elif "filename" in entry:
        files_to_verify = [{"filename": entry["filename"], "sha256": entry.get("sha256", "")}]

    for f in files_to_verify:
        path = calc.mount_path / f["filename"]
        if not path.exists():
            raise RuntimeError(
                f"File '{f['filename']}' not found on calculator. "
                f"It may have been deleted manually."
            )
        actual = _sha256(path.read_bytes())
        if actual != f.get("sha256", ""):
            return False
    return True