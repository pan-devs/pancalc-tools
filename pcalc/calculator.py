"""
pcalc/calculator.py — Detect a connected Casio Prizm calculator via USB mass storage.
Works on Linux, macOS and Windows by scanning mounted drives for Casio-specific folders.
"""

import os
import platform
import shutil
import subprocess
from pathlib import Path
from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Folders that exist on the root of a Casio Prizm storage
CASIO_MARKERS = ["@MainMem", "@Backup", "@SAVE_F"]

# Known model names by marker files/folders (best-effort)
MODEL_HINTS = {
    "fx-CG50":  ["@MainMem"],
    "fx-CG100": ["@MainMem"],
}


# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@dataclass
class Calculator:
    model: str          # e.g. "fx-CG50" (best-effort)
    mount_path: Path    # e.g. Path("/media/user/CASIO")
    storage_total: int  # bytes
    storage_free:  int  # bytes

    @property
    def storage_used(self) -> int:
        return self.storage_total - self.storage_free

    @property
    def storage_total_mb(self) -> float:
        return self.storage_total / (1024 * 1024)

    @property
    def storage_free_mb(self) -> float:
        return self.storage_free / (1024 * 1024)

    @property
    def storage_used_mb(self) -> float:
        return self.storage_used / (1024 * 1024)


# ---------------------------------------------------------------------------
# Platform-specific mount point discovery
# ---------------------------------------------------------------------------

def _candidate_paths_linux() -> list[Path]:
    """Return candidate mount points on Linux."""
    candidates = []

    # /media/<user>/* /media/<mount> and /run/media/<user>/* /run/media/<mount>
    for base in [Path("/media"), Path("/run/media")]:
        if base.exists():
            for entry in base.iterdir():
                if entry.is_dir():
                    candidates.append(entry)
                    candidates.extend(p for p in entry.iterdir() if p.is_dir())

    # /mnt/*
    mnt = Path("/mnt")
    if mnt.exists():
        candidates.extend(p for p in mnt.iterdir() if p.is_dir())

    return candidates


def _candidate_paths_macos() -> list[Path]:
    """Return candidate mount points on macOS."""
    volumes = Path("/Volumes")
    if not volumes.exists():
        return []
    return [p for p in volumes.iterdir() if p.is_dir()]


def _candidate_paths_windows() -> list[Path]:
    """Return candidate drive letters on Windows."""
    candidates = []
    # Scan all drive letters A-Z
    for letter in "ABCDEFGHIJKLMNOPQRSTUVWXYZ":
        drive = Path(f"{letter}:\\")
        if drive.exists():
            candidates.append(drive)
    return candidates


def _get_candidates() -> list[Path]:
    system = platform.system()
    if system == "Linux":
        return _candidate_paths_linux()
    elif system == "Darwin":
        return _candidate_paths_macos()
    elif system == "Windows":
        return _candidate_paths_windows()
    return []


# ---------------------------------------------------------------------------
# Detection logic
# ---------------------------------------------------------------------------

def _is_casio(path: Path) -> bool:
    """Return True if the given path looks like a Casio Prizm storage."""
    try:
        entries = [e.name for e in path.iterdir()]
    except (PermissionError, OSError):
        return False
    entries_lower = [e.lower() for e in entries]
    return any(marker.lower() in entries_lower for marker in CASIO_MARKERS)


def _detect_model(path: Path) -> str:
    """Best-effort model detection based on folder structure."""
    try:
        entries = [e.name for e in path.iterdir()]
    except (PermissionError, OSError):
        return "Casio Prizm"

    # fx-CG100 has a @MainMem folder AND typically more storage
    usage = shutil.disk_usage(path)
    total_mb = usage.total / (1024 * 1024)

    # fx-CG50 ~ 16 MB internal, fx-CG100 ~ 32 MB
    if total_mb > 24:
        return "fx-CG100"
    return "fx-CG50"


def _calc_from_path(path: Path) -> Calculator | None:
    if not _is_casio(path):
        return None
    try:
        usage = shutil.disk_usage(path)
    except OSError:
        return None
    model = _detect_model(path)
    return Calculator(
        model=model,
        mount_path=path,
        storage_total=usage.total,
        storage_free=usage.free,
    )


def _auto_mount_casio() -> Path | None:
    """
    Try to auto-mount an unmounted Casio device via udisksctl.
    Returns the mount point path if successful, None otherwise.
    """
    if platform.system() != "Linux":
        return None

    try:
        result = subprocess.run(
            ["lsblk", "-o", "NAME,FSTYPE,SIZE,MOUNTPOINT", "-n", "-l", "-b"],
            capture_output=True, text=True, timeout=10
        )
    except Exception:
        return None

    for line in result.stdout.strip().split("\n"):
        parts = line.split()
        if len(parts) < 3:
            continue
        name, fstype, size_str = parts[0], parts[1], parts[2]
        mountpoint = parts[3] if len(parts) > 3 else ""
        if mountpoint or fstype not in ("vfat", "exfat"):
            continue
        try:
            if int(size_str) > 64 * 1024 * 1024:
                continue
        except ValueError:
            continue

        dev = f"/dev/{name}"
        try:
            subprocess.run(
                ["udisksctl", "mount", "-b", dev],
                check=True, capture_output=True, timeout=10
            )
            result2 = subprocess.run(
                ["findmnt", "-n", "-o", "TARGET", dev],
                capture_output=True, text=True, timeout=5
            )
            mount_path = result2.stdout.strip()
            if mount_path:
                return Path(mount_path)
        except Exception:
            continue

    return None


def find_calculator() -> Calculator | None:
    """
    Scan mounted drives for a connected Casio Prizm calculator.
    Falls back to auto-mounting via udisksctl if no mounted device is found.

    Returns:
        A Calculator instance if found, None otherwise.
    """
    for path in _get_candidates():
        calc = _calc_from_path(path)
        if calc:
            return calc

    if platform.system() == "Linux":
        _ensure_udisksctl()
        mount_path = _auto_mount_casio()
        if mount_path:
            calc = _calc_from_path(mount_path)
            if calc:
                return calc

    return None


def require_calculator() -> Calculator:
    """
    Like find_calculator(), but raises if no calculator is found.

    Returns:
        A Calculator instance.

    Raises:
        RuntimeError: If no calculator is connected.
    """
    calc = find_calculator()
    if calc is None:
        raise RuntimeError(
            "No calculator detected. Connect your fx-CG50 via USB and press F1 "
            "to enable USB mass storage mode, then try again."
        )
    return calc


# ---------------------------------------------------------------------------
# System dependency auto-install
# ---------------------------------------------------------------------------


def _detect_pkg_manager() -> str | None:
    """Detect the system package manager install command."""
    if platform.system() != "Linux":
        return None
    if shutil.which("apt") or os.path.exists("/etc/debian_version"):
        return "apt install -y"
    if shutil.which("pacman"):
        return "pacman -S --noconfirm"
    if shutil.which("dnf"):
        return "dnf install -y"
    if shutil.which("yum"):
        return "yum install -y"
    if shutil.which("zypper"):
        return "zypper install -y"
    return None


def _ensure_udisksctl() -> bool:
    """
    Check if udisksctl is available. If not, explain why it's needed
    and offer to install it.
    """
    if shutil.which("udisksctl"):
        return True

    print()
    print("  ⚠  udisksctl not found")
    print("  ──────────────────────")
    print("  udisksctl is needed to auto-mount the calculator when it is")
    print("  not already mounted. Without it, connect the calculator before")
    print("  launching the program or mount it manually.")
    print()

    pm = _detect_pkg_manager()
    if not pm:
        print("  Install udisks2 manually for your distribution.")
        print("  Example:  sudo apt install udisks2")
        print()
        return False

    cmd = f"sudo {pm} udisks2"
    print(f"  Installing: {cmd}")
    print("  (you will be prompted for your sudo password)")
    print()
    try:
        subprocess.run(cmd.split(), check=True)
        print()
        return shutil.which("udisksctl") is not None
    except subprocess.CalledProcessError:
        print("  Failed to install udisks2. Install it manually:")
        print(f"    {cmd}")
        print()
        return False
    except KeyboardInterrupt:
        print("  Cancelled.")
        print()
        return False