"""
pcalc/updater.py — self-update helpers for the PanCalc Tools GUI.

Checks GitHub Releases for a newer version of the app and downloads the
platform installer so the GUI can offer an in-app update with progress.
"""
from __future__ import annotations
import os
import re
import sys
from pathlib import Path

from pcalc import __version__

REPO = "pan-devs/pancalc-tools"
RELEASES_LATEST_URL = f"https://api.github.com/repos/{REPO}/releases/latest"

_PLATFORM_EXTS = {
    "nt": ".exe",
    "darwin": ".dmg",
    "linux": ".AppImage",
}


def _parse_version(value: str) -> tuple:
    """Parse '0.2.4', 'v0.2.5', '0.2.4-dev' into a comparable (major, minor, patch)."""
    s = (value or "").strip().lower().lstrip("v")
    parts: list[int] = []
    for chunk in re.split(r"[^\d]+", s):
        if chunk.isdigit():
            parts.append(int(chunk))
        elif chunk == "":
            continue
        else:
            break
    while len(parts) < 3:
        parts.append(0)
    return tuple(parts[:3])


def installer_ext() -> str:
    """File extension of the installer for the current platform."""
    return _PLATFORM_EXTS.get("nt" if os.name == "nt" else sys.platform, ".exe")


def current_version() -> str:
    """Best-guess version of the running app.

    Priority: a bundled version.txt (frozen builds ship it next to the exe),
    then an optional version.txt at the repo root (dev), then the installed
    package metadata fallback.
    """
    candidates: list[Path] = []
    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "version.txt")
    candidates.append(Path(__file__).resolve().parent.parent / "version.txt")
    for candidate in candidates:
        try:
            if candidate.is_file():
                text = candidate.read_text(encoding="utf-8").strip()
                if text:
                    return text
        except OSError:
            continue
    return __version__


def latest_release(timeout: float = 6.0) -> dict | None:
    """Fetch the latest GitHub release.

    Returns:
        {"version": str, "url": str, "name": str} if a newer release is
        reachable, otherwise None (offline, no release yet, or API error).
    """
    try:
        import requests

        response = requests.get(RELEASES_LATEST_URL, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None
    tag = str(data.get("tag_name", "")).strip().lstrip("v")
    if not tag:
        return None
    ext = installer_ext()
    url: str | None = None
    for asset in data.get("assets") or []:
        name = str(asset.get("name", ""))
        asset_url = asset.get("browser_download_url", "")
        if name.lower().endswith(ext) and asset_url:
            url = asset_url
            break
    if not url:
        url = data.get("html_url")
    return {"version": tag, "url": url, "name": str(data.get("name", ""))}


def update_available(current: str | None = None, latest: str | None = None) -> bool:
    """True when the latest release is strictly newer than the running app."""
    current = current_version() if current is None else current
    if latest is None:
        release = latest_release()
        if not release:
            return False
        latest_version = release["version"]
    else:
        latest_version = latest
    return _parse_version(latest_version) > _parse_version(current)


def download(url: str, dest: Path, progress_callback=None) -> Path:
    """Stream a release installer to disk with optional progress updates.

    Args:
        url: Download URL (https or file://).
        dest: Destination path (a .part temp file is used while downloading).
        progress_callback: Optional callable(downloaded, total, label).

    Raises:
        RuntimeError: On network, timeout, or HTTP errors.
    """
    if url.startswith("file://"):
        import urllib.parse

        parsed = urllib.parse.urlparse(url)
        path_str = parsed.path
        if os.name == "nt" and path_str.startswith("/"):
            path_str = path_str[1:]
        src = Path(urllib.parse.unquote(path_str))
        if not src.is_file():
            raise RuntimeError(f"Local file not found: {src}")
        dest.parent.mkdir(parents=True, exist_ok=True)
        with open(src, "rb") as fh:
            data = fh.read()
        dest.write_bytes(data)
        return dest

    try:
        import requests

        response = requests.get(url, stream=True, timeout=60)
        response.raise_for_status()
    except requests.exceptions.ConnectionError as exc:
        raise RuntimeError("No internet connection while downloading the update.") from exc
    except requests.exceptions.Timeout as exc:
        raise RuntimeError("Update download timed out.") from exc
    except requests.exceptions.HTTPError as exc:
        raise RuntimeError(f"HTTP error downloading the update: {exc}") from exc

    total = int(response.headers.get("content-length", 0))
    downloaded = 0
    dest.parent.mkdir(parents=True, exist_ok=True)
    part = dest.with_suffix(dest.suffix + ".part")
    try:
        with open(part, "wb") as fh:
            for chunk in response.iter_content(chunk_size=1 << 16):
                if not chunk:
                    continue
                fh.write(chunk)
                downloaded += len(chunk)
                if progress_callback:
                    progress_callback(downloaded, total, "PanCalc Tools")
        part.replace(dest)
    finally:
        try:
            if part.exists():
                part.unlink()
        except OSError:
            pass
    return dest