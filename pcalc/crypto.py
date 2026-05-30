"""
pcalc/crypto.py — SHA256 and PGP signature verification.

PGP: verification is always done against the official Pan Devs key,
downloaded automatically from the registry. No manual import/trust needed.
"""

import hashlib
import io
import json
import os
import platform
import shutil
import subprocess
import tempfile
import urllib.request
from pathlib import Path
from platformdirs import user_cache_dir

import gnupg

GNUPG_DIR = Path(user_cache_dir("pancalc")) / "gnupg"
TRUSTED_FILE = Path(user_cache_dir("pancalc")) / "trusted-keys.json"

OFFICIAL_KEY_URL = "https://raw.githubusercontent.com/pan-devs/pancalc-registry/main/pandevs.asc"
OFFICIAL_KEY_ID = "1A370E1B68A194A8"  # fingerprint suffix of the Pan Devs key


_GPG_CHECKED = False


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


def _ensure_gpg() -> bool:
    """
    Check if gpg is available. If not, prompt the user to install it
    and attempt auto-install on Windows/macOS/Linux.
    """
    if shutil.which("gpg"):
        return True

    print()
    print("  ⚠  GPG (GnuPG) not found")
    print("  ────────────────────────")
    print("  PGP signature verification requires the gpg command.")
    print("  Without it, PGP keys and verification are skipped.")
    print()

    system = platform.system()
    if system == "Windows":
        if shutil.which("winget"):
            print("  Attempting to install via winget...")
            try:
                subprocess.run(
                    ["winget", "install", "GnuPG.GnuPG", "--silent", "--accept-package-agreements"],
                    check=True,
                )
                print()
                return shutil.which("gpg") is not None
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
        print("  Install Gpg4win manually from https://gpg4win.org")
        print()

    elif system == "Darwin":
        if shutil.which("brew"):
            print("  Attempting to install via Homebrew...")
            try:
                subprocess.run(["brew", "install", "gnupg"], check=True)
                print()
                return shutil.which("gpg") is not None
            except subprocess.CalledProcessError:
                pass
        print("  Install GPG manually:  brew install gnupg")
        print()

    else:  # Linux
        pm = _detect_pkg_manager()
        if pm:
            cmd = f"sudo {pm} gnupg"
            print(f"  Attempting to install: {cmd}")
            print("  (you may be prompted for your sudo password)")
            print()
            try:
                subprocess.run(cmd.split(), check=True)
                print()
                return shutil.which("gpg") is not None
            except (subprocess.CalledProcessError, FileNotFoundError):
                pass
        print("  Install GPG manually via your package manager.")
        print("  Example:  sudo apt install gnupg")
        print()

    return False


def _gpg():
    GNUPG_DIR.mkdir(parents=True, exist_ok=True)
    global _GPG_CHECKED
    if not _GPG_CHECKED:
        _GPG_CHECKED = True
        _ensure_gpg()

    gpgbinary = None
    if platform.system() == "Windows":
        common_paths = [
            "C:\\Program Files\\GnuPG\\bin\\gpg.exe",
            "C:\\Program Files (x86)\\GnuPG\\bin\\gpg.exe",
            "C:\\Program Files\\Gpg4win\\bin\\gpg.exe",
        ]
        for path in common_paths:
            if Path(path).exists():
                gpgbinary = path
                break

    try:
        return gnupg.GPG(gnupghome=str(GNUPG_DIR), gpgbinary=gpgbinary)
    except OSError:
        return None


# ── SHA256 ──────────────────────────────────────────────────────────


def sha256_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_sha256(data: bytes, expected: str) -> bool:
    return sha256_digest(data) == expected.lower()


# ── Official Pan Devs key ──────────────────────────────────────────


def _ensure_official_key() -> str | None:
    """Download & import the official Pan Devs PGP key if not cached yet.
    Returns the key's fingerprint, or None on failure."""
    print("[_ensure_official_key] START")
    gpg = _gpg()
    if gpg is None:
        print("[_ensure_official_key] _gpg() returned None — GNUPG_DIR exists:", GNUPG_DIR.exists(), "| dir:", GNUPG_DIR)
        return None
    print("[_ensure_official_key] _gpg() OK — gpgbinary:", getattr(gpg, 'gpgbinary', 'default'))

    # Already imported?
    for k in gpg.list_keys():
        fp = k["fingerprint"]
        if fp.endswith(OFFICIAL_KEY_ID):
            print("[_ensure_official_key] key already imported:", fp)
            return fp
    print("[_ensure_official_key] key not cached, downloading...")

    # Download from registry
    try:
        print("[_ensure_official_key] fetching:", OFFICIAL_KEY_URL)
        with urllib.request.urlopen(OFFICIAL_KEY_URL, timeout=10) as r:
            key_data = r.read().decode("utf-8")
        print("[_ensure_official_key] download OK —", len(key_data), "bytes")
    except Exception as exc:
        print("[_ensure_official_key] download failed:", type(exc).__name__, exc)
        return None

    print("[_ensure_official_key] calling gpg.import_keys()...")
    result = gpg.import_keys(key_data)
    print("[_ensure_official_key] import_keys done — count:", result.count, "| fingerprints:", result.fingerprints if result.fingerprints else "[]")
    if result.count == 0:
        return None
    fp = result.fingerprints[0]
    # Trust ultimately so python-gnupg reports trust_level
    gpg.trust_keys(fp, "TRUST_ULTIMATE")
    print("[_ensure_official_key] DONE — fingerprint:", fp)
    return fp


def official_key_info() -> dict | None:
    """Return info about the official Pan Devs key if imported."""
    gpg = _gpg()
    if gpg is None:
        return None
    for k in gpg.list_keys():
        fp = k["fingerprint"]
        if fp.endswith(OFFICIAL_KEY_ID):
            return {
                "keyid": k["keyid"],
                "fingerprint": fp,
                "uids": k["uids"],
            }
    return None


# ── Signature verification ─────────────────────────────────────────


def verify_official_signature(data: bytes, signature_asc: str) -> bool:
    """Verify a detached PGP signature against the official Pan Devs key.

    The official key is downloaded & cached automatically from the registry.
    Returns True only if the signature is valid *and* was made by the
    official key.
    """
    official_fp = _ensure_official_key()
    if official_fp is None:
        return False

    gpg = _gpg()
    # verify_file(sig, data_path): first arg is the signature (file-like),
    # second is the path to the data (for detached sigs).
    data_tmp = tempfile.NamedTemporaryFile(delete=False)
    data_tmp.write(data)
    data_tmp.close()
    try:
        verified = gpg.verify_file(io.BytesIO(signature_asc.encode()), data_tmp.name)
    finally:
        os.unlink(data_tmp.name)
    if verified and verified.fingerprint == official_fp:
        return True
    return False


# ── Legacy key management (advanced users) ─────────────────────────


def import_key(key_path: str) -> dict:
    """Import a PGP public key file. Returns {'fingerprint': ..., 'keyid': ...}."""
    gpg = _gpg()
    if gpg is None:
        raise RuntimeError("GPG is not available. Install Gpg4win from https://gpg4win.org and try again.")
    key_data = Path(key_path).read_text()
    result = gpg.import_keys(key_data)
    if result.count == 0:
        raise RuntimeError("Failed to import key — file may be invalid.")
    fp = result.fingerprints[0]
    keyid = fp[-16:]
    trusted = _load_trusted()
    trusted[fp] = {"fingerprint": fp, "keyid": keyid, "trusted": False}
    _save_trusted(trusted)
    return {"fingerprint": fp, "keyid": keyid}


def list_keys() -> list[dict]:
    """List all keys in the pancalc keyring with trust status."""
    gpg = _gpg()
    if gpg is None:
        return []
    trusted = _load_trusted()
    result = []
    for k in gpg.list_keys():
        fp = k["fingerprint"]
        is_official = fp.endswith(OFFICIAL_KEY_ID)
        result.append({
            "keyid": k["keyid"],
            "fingerprint": fp,
            "uids": k["uids"],
            "trusted": is_official or (fp in trusted and trusted[fp].get("trusted", False)),
            "official": is_official,
        })
    return result


def trust_key(fingerprint: str) -> bool:
    """Mark a key as trusted for signature verification."""
    gpg = _gpg()
    if gpg is None:
        raise RuntimeError("GPG is not available. Install Gpg4win from https://gpg4win.org and try again.")
    trusted = _load_trusted()
    if fingerprint not in trusted:
        keys = gpg.list_keys()
        found = any(k["fingerprint"] == fingerprint for k in keys)
        if not found:
            raise RuntimeError(f"Key {fingerprint} not found. Import it first with 'import-key'.")
        trusted[fingerprint] = {"fingerprint": fingerprint, "trusted": False}
    gpg.trust_keys(fingerprint, "TRUST_ULTIMATE")
    trusted[fingerprint]["trusted"] = True
    _save_trusted(trusted)
    return True


def untrust_key(fingerprint: str) -> bool:
    trusted = _load_trusted()
    if fingerprint in trusted:
        trusted[fingerprint]["trusted"] = False
        _save_trusted(trusted)
    return True


def get_trusted_fingerprints() -> list[str]:
    trusted = _load_trusted()
    return [fp for fp, info in trusted.items() if info.get("trusted", False)]


def _load_trusted() -> dict:
    if TRUSTED_FILE.exists():
        return json.loads(TRUSTED_FILE.read_text())
    return {}


def _save_trusted(keys: dict):
    TRUSTED_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRUSTED_FILE.write_text(json.dumps(keys, indent=2))


# ── Legacy verify (still used elsewhere?) ──────────────────────────


def verify_signature(data: bytes, signature_asc: str) -> str | None:
    """Verify a detached PGP signature.

    Returns the signer's fingerprint on success, or None if verification fails.
    """
    gpg = _gpg()
    if gpg is None:
        return None
    data_tmp = tempfile.NamedTemporaryFile(delete=False)
    data_tmp.write(data)
    data_tmp.close()
    try:
        verified = gpg.verify_file(io.BytesIO(signature_asc.encode()), data_tmp.name)
    finally:
        os.unlink(data_tmp.name)
    if verified and verified.trust_level is not None:
        return verified.fingerprint
    return None


def is_trusted_signature(data: bytes, signature_asc: str) -> bool:
    """Verify a detached PGP signature against any trusted key."""
    fp = verify_signature(data, signature_asc)
    if fp is None:
        return False
    trusted_fps = get_trusted_fingerprints()
    return fp in trusted_fps
