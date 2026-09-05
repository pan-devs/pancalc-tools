"""
pcalc/installer.py — Install, remove and track add-ins on a connected Casio Prizm.
Handles direct .g3a downloads and zip archives containing .g3a files.
"""

import hashlib
import io
import json
import os
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path

import requests
from platformdirs import user_cache_dir

from pcalc.calculator import Calculator
from pcalc.crypto import verify_official_signature, sha256_digest, verify_sha256


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

INSTALLED_FILE = Path(user_cache_dir("pancalc")) / "installed.json"
CHUNK_SIZE     = 8192  # bytes per download chunk


# ---------------------------------------------------------------------------
# Device scanner
# ---------------------------------------------------------------------------

@dataclass
class DeviceFile:
    filename: str
    path: Path
    size: int
    addin: dict | None = None


@dataclass
class CalcEntry:
    name: str
    rel_path: str
    path: Path
    size: int
    is_dir: bool
    addin: dict | None = None
    children: list['CalcEntry'] | None = None


def _match_addin_by_filename(filename: str, addins: list[dict]) -> dict | None:
    """Return the add-in that this filename belongs to, or None."""
    fname_lower = filename.lower()
    for addin in addins:
        files_list = addin.get("files", None)
        if files_list:
            for f in files_list:
                if f.get("filename", "").lower() == fname_lower:
                    return addin
        else:
            legacy = addin.get("filename") or addin.get("zip_file") or Path(addin.get("download_url", "")).name
            if legacy.lower() == fname_lower:
                return addin
    return None


def scan_device(calc: Calculator, addins: list[dict] | None = None) -> list[DeviceFile]:
    """Scan the calculator filesystem and return all files, matched against known add-ins/games."""
    from pcalc import registry as _reg
    if addins is None:
        try:
            addins = _reg.get_registry()
        except RuntimeError:
            addins = []
    else:
        # Create a copy so we don't mutate the caller's list
        addins = list(addins)

    try:
        games = _reg.get_games()
        addin_ids = {a.get("id") for a in addins}
        for g in games:
            if g.get("id") not in addin_ids:
                addins.append(g)
    except Exception:
        pass

    results: list[DeviceFile] = []
    try:
        for entry in calc.mount_path.iterdir():
            if entry.is_file():
                df = DeviceFile(
                    filename=entry.name,
                    path=entry,
                    size=entry.stat().st_size,
                    addin=_match_addin_by_filename(entry.name, addins),
                )
                results.append(df)
    except OSError:
        pass

    results.sort(key=lambda x: (0 if x.addin else 1, x.filename.lower()))
    return results


def walk_calc(calc: Calculator, addins: list[dict] | None = None,
              max_depth: int = 8) -> list[CalcEntry]:
    """Recursively walk the calculator mount and return a tree of CalcEntry."""
    from pcalc import registry as _reg
    if addins is None:
        try:
            addins = _reg.get_registry()
        except RuntimeError:
            addins = []
    else:
        # Create a copy so we don't mutate the caller's list
        addins = list(addins)

    try:
        games = _reg.get_games()
        addin_ids = {a.get("id") for a in addins}
        for g in games:
            if g.get("id") not in addin_ids:
                addins.append(g)
    except Exception:
        pass

    def _walk(dir_path: Path, rel_base: str, depth: int) -> list[CalcEntry]:
        if depth > max_depth:
            return []
        entries: list[CalcEntry] = []
        try:
            for entry in sorted(dir_path.iterdir(), key=lambda p: (not p.is_dir(), p.name.lower())):
                rel = f"{rel_base}/{entry.name}" if rel_base else entry.name
                if entry.is_dir():
                    children = _walk(entry, rel, depth + 1)
                    entries.append(CalcEntry(
                        name=entry.name, rel_path=rel, path=entry,
                        size=0, is_dir=True, addin=None, children=children,
                    ))
                elif entry.is_file():
                    entries.append(CalcEntry(
                        name=entry.name, rel_path=rel, path=entry,
                        size=entry.stat().st_size, is_dir=False,
                        addin=_match_addin_by_filename(entry.name, addins),
                    ))
        except (PermissionError, OSError):
            pass
        return entries

    return _walk(calc.mount_path, "", 0)


def iter_calc_files(entries: list[CalcEntry]):
    """Yield all non-directory CalcEntry from a tree."""
    for e in entries:
        if e.is_dir and e.children:
            yield from iter_calc_files(e.children)
        elif not e.is_dir:
            yield e


def count_calc_files(entries: list[CalcEntry]) -> int:
    """Count total files (non-directory) in a CalcEntry tree."""
    total = 0
    for e in entries:
        if e.is_dir and e.children:
            total += count_calc_files(e.children)
        elif not e.is_dir:
            total += 1
    return total


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

def _download_bytes(url: str, progress_callback=None, cb_label: str = "") -> bytes:
    """
    Download a file from a URL and return its raw bytes.
    Optionally calls progress_callback(downloaded, total, label) per chunk.

    Args:
        url: Download URL.
        progress_callback: Optional callable(current, total, label).
        cb_label: Label passed to callback so the caller knows which file.

    Raises:
        RuntimeError: On network or HTTP errors.
    """
    if url.startswith("file://"):
        import urllib.parse
        parsed = urllib.parse.urlparse(url)
        path_str = parsed.path
        if os.name == 'nt' and path_str.startswith('/'):
            path_str = path_str[1:]
        p = Path(urllib.parse.unquote(path_str))
        if not p.exists():
            raise RuntimeError(f"Local file not found: {p}")
        return p.read_bytes()
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
                progress_callback(downloaded, total, cb_label)

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
            # Match basename (handle files inside subdirectories like "dir/Geometry.g3a")
            for name in names:
                if Path(name).name.lower() == zip_file.lower():
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
    # Local file — convert path to file:// URL
    if "local_path" in addin:
        entry = {
            "download_url": Path(addin["local_path"]).as_uri(),
            "download_type": "direct",
            "filename": addin.get("filename", Path(addin["local_path"]).name),
        }
        if "sha256" in addin:
            entry["sha256"] = addin["sha256"]
        return [entry]

    if "files" in addin:
        return addin["files"]

    addin_id = addin["id"]
    dl_url   = addin["download_url"]
    dl_type  = addin.get("download_type", "direct")
    zip_file = addin.get("zip_file", f"{addin_id}.g3a")

    entry = {
        "download_url": dl_url,
        "download_type": dl_type,
        "zip_file": zip_file,
    }
    if "filename" in addin:
        entry["filename"] = addin["filename"]
    if "sha256" in addin:
        entry["sha256"] = addin["sha256"]
    if "signature_url" in addin:
        entry["signature_url"] = addin["signature_url"]
    return [entry]


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


def install(addin: dict, calc: Calculator, progress_callback=None, write_callback=None,
            skip_files: set[str] | None = None) -> list[Path]:
    """
    Download and install one or more add-in files to the connected calculator.

    Args:
        addin: Add-in dict from the registry.
        calc: Connected Calculator instance.
        progress_callback: Optional callable(downloaded, total) for download progress.
        write_callback: Optional callable(filename, written, total) for write progress.
        skip_files: Optional set of filenames to skip (e.g. when user chose not to overwrite).

    Returns:
        List of Paths to the installed files on the calculator.

    Raises:
        RuntimeError: On download, extraction, or copy errors.
    """
    addin_id = addin["id"]
    name     = addin.get("name", addin_id)

    files_info = _get_addin_files(addin)
    installed_paths = []

    installed = _load_installed()
    prev_files = installed.get(addin_id, {}).get("files")
    file_records = list(prev_files) if isinstance(prev_files, list) else []

    for i, file_info in enumerate(files_info):
        dl_url  = file_info["download_url"]
        dl_type = file_info.get("download_type", "direct")
        zip_file = file_info.get("zip_file", f"{addin_id}.g3a")
        filename = _resolve_file_name(file_info, addin_id)

        # Skip files the user chose not to overwrite
        if skip_files and filename in skip_files:
            continue

        # Download
        raw = _download_bytes(dl_url, progress_callback=progress_callback, cb_label=filename)

        # PGP signature verification (optional — against official Pan Devs key)
        default_sig_url = dl_url + ".asc"
        sig_url = file_info.get("signature_url", default_sig_url)
        # Only try the default "<download_url>.asc" as a fallback when it is
        # a different URL than the registry's signature_url (avoids re-downloading
        # the same file twice on verification failure).
        sig_candidates = [sig_url]
        if sig_url != default_sig_url:
            sig_candidates.append(default_sig_url)
        signature_downloaded = False
        signature_ok = False
        for candidate in sig_candidates:
            try:
                sig_data = _download_bytes(candidate)
            except RuntimeError:
                continue
            signature_downloaded = True
            if verify_official_signature(raw, sig_data.decode("utf-8", errors="replace")):
                signature_ok = True
                break
        if signature_downloaded and not signature_ok:
            raise RuntimeError(
                f"PGP signature verification failed for {filename}. "
                "The file may be corrupted or untrusted."
            )

        # Extract from zip if needed
        if dl_type == "zip":
            g3a_bytes = _extract_g3a_from_zip(raw, zip_file)
        else:
            g3a_bytes = raw

        # SHA256 verification (optional — if sha256 is present in registry)
        # Verified against the final .g3a (after extraction, if applicable)
        if "sha256" in file_info:
            expected_sha = file_info["sha256"]
            if not verify_sha256(g3a_bytes, expected_sha):
                raise RuntimeError(
                    f"SHA256 mismatch for {filename}: "
                    f"expected {expected_sha}, got {sha256_digest(g3a_bytes)}"
                )

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

        # Persist incrementally after each file so a partial multi-file install
        # is still tracked — otherwise a failure mid-batch would leave files on
        # the calculator that verify/remove would not know about.
        installed[addin_id] = {
            "id":         addin_id,
            "name":       name,
            "version":    addin.get("version", "unknown"),
            "files":      list(file_records),
            "mount_path": str(calc.mount_path),
        }
        _save_installed(installed)

    return installed_paths


SAVE_EXTS = {'.sav', '.srm', '.state', '.sgm', '.frz'}


def _clean_save_files(rom_path: Path) -> None:
    """Delete companion save/state files for a ROM file.

    Checks:
    1. Same stem + save extension (zelda.nes → zelda.sav)
    2. Appended extension (zelda.nes → zelda.nes.sav)
    3. Case-insensitive stem match in the same directory
    """
    stem = rom_path.stem
    parent = rom_path.parent

    for ext in SAVE_EXTS:
        # Pattern: same stem, different extension
        p = rom_path.with_suffix(ext)
        if p.exists() and p.is_file():
            try:
                p.unlink()
            except OSError:
                pass
        # Pattern: appended extension
        p = Path(str(rom_path) + ext)
        if p.exists() and p.is_file():
            try:
                p.unlink()
            except OSError:
                pass

    # Case-insensitive stem match in directory (handles sanitize mismatches)
    try:
        for f in parent.iterdir():
            if f.is_file() and f.suffix.lower() in SAVE_EXTS:
                if f.stem.lower() == stem.lower():
                    try:
                        f.unlink()
                    except OSError:
                        pass
    except OSError:
        pass


def remove(addin_id: str, calc: Calculator) -> None:
    """
    Remove an installed add-in from the calculator and the local database.

    If the add-in is not tracked in installed.json, falls back to scanning
    the device and matching against the registry (like verify_addin does).

    Args:
        addin_id: ID of the add-in to remove.
        calc: Connected Calculator instance.

    Raises:
        RuntimeError: If the add-in is not installed or file cannot be deleted.
    """
    installed = _load_installed()
    if addin_id in installed:
        entry = installed[addin_id]

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
            _clean_save_files(path)

        del installed[addin_id]
        _save_installed(installed)
        return

    # Fallback: not in installed.json — scan device and match against registry
    from pcalc import registry as _reg
    try:
        addins = _reg.get_registry()
    except RuntimeError:
        addins = []

    addin = None
    for a in addins:
        if a.get("id", "").lower() == addin_id.lower():
            addin = a
            break

    if not addin:
        raise RuntimeError(f"'{addin_id}' is not installed.")

    files_to_remove = []
    if "files" in addin:
        files_to_remove = [f["filename"] for f in addin["files"]]
    elif "local_path" in addin:
        fname = addin.get("filename") or Path(addin["local_path"]).name
        files_to_remove = [fname]
    else:
        fname = addin.get("zip_file") or Path(addin.get("download_url", "")).name
        files_to_remove = [fname]

    deleted_any = False
    for filename in files_to_remove:
        path = calc.mount_path / filename
        if path.exists():
            try:
                path.unlink()
                deleted_any = True
            except OSError as e:
                raise RuntimeError(f"Failed to remove '{filename}' from calculator: {e}")
        # Delete companion save files
        _clean_save_files(path)

    if not deleted_any:
        raise RuntimeError(f"'{addin_id}' is not installed.")


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
        try:
            actual = _sha256(path.read_bytes())
        except OSError as e:
            raise RuntimeError(
                f"Failed to read '{f['filename']}' from calculator: {e}"
            )
        if actual != f["sha256"]:
            return False
    return True


def verify_addin(addin: dict, calc: Calculator) -> bool:
    """
    Verify an add-in by scanning the calculator directly, no local cache needed.

    For zip-type addins, downloads the zip and computes the SHA of the extracted file.

    Args:
        addin: Add-in dictionary from registry.
        calc: Connected Calculator instance.

    Returns:
        True if all checksums match, False otherwise.

    Raises:
        RuntimeError: If files cannot be read or are missing.
    """
    aid = addin.get("id", "")
    addin_id = aid
    files_to_verify: list[dict] = []

    # Local entry (user-imported file) — has local_path, filename, sha256
    if "local_path" in addin:
        fname = addin.get("filename") or Path(addin["local_path"]).name
        sha = addin.get("sha256", "")
        if sha:
            files_to_verify = [{"filename": fname, "sha256": sha}]
        else:
            raise RuntimeError(f"No SHA256 checksum available for local add-in '{aid}'.")

    elif "files" in addin:
        # Multi-file addin (e.g. KhiCAS): each entry has filename + sha256
        files_to_verify = [
            {"filename": f["filename"], "sha256": f["sha256"]}
            for f in addin["files"] if "sha256" in f
        ]
    else:
        # Single-file addin — determine filename and expected SHA
        fname = addin.get("zip_file") or Path(addin.get("download_url", "")).name
        if addin.get("download_type") == "zip":
            # Download the zip, extract the g3a, verify its SHA
            dl_url = addin["download_url"]
            zip_file = addin.get("zip_file", f"{addin_id}.g3a")
            try:
                zip_bytes = _download_bytes(dl_url)
            except RuntimeError as e:
                raise RuntimeError(f"Failed to download '{aid}' for verification: {e}")
            g3a_bytes = _extract_g3a_from_zip(zip_bytes, zip_file)
            g3a_sha = _sha256(g3a_bytes)
            # Verify extracted .g3a SHA if present in registry
            sha = addin.get("sha256", "")
            if sha and g3a_sha != sha:
                raise RuntimeError(f"Extracted .g3a for '{aid}' failed SHA256 check.")
            files_to_verify = [{"filename": fname, "sha256": g3a_sha}]
        else:
            sha = addin.get("sha256", "")
            if sha:
                files_to_verify = [{"filename": fname, "sha256": sha}]

    if not files_to_verify:
        raise RuntimeError(f"No SHA256 checksums available to verify '{aid}'.")

    for f in files_to_verify:
        path = calc.mount_path / f["filename"]
        if not path.exists():
            raise RuntimeError(
                f"File '{f['filename']}' not found on calculator "
                f"for add-in '{aid}'."
            )
        try:
            actual = _sha256(path.read_bytes())
        except OSError as e:
            raise RuntimeError(
                f"Failed to read '{f['filename']}' from calculator: {e}"
            )
        if f["sha256"] and actual != f["sha256"]:
            return False
    return True