"""
pcalc/crypto.py — SHA256 and PGP signature verification.
"""

import hashlib
import json
from pathlib import Path
from platformdirs import user_cache_dir

import gnupg

GNUPG_DIR = Path(user_cache_dir("pancalc")) / "gnupg"
TRUSTED_FILE = Path(user_cache_dir("pancalc")) / "trusted-keys.json"


def _gpg():
    GNUPG_DIR.mkdir(parents=True, exist_ok=True)
    return gnupg.GPG(gnupghome=str(GNUPG_DIR))


# ── SHA256 ──────────────────────────────────────────────────────────


def sha256_digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def verify_sha256(data: bytes, expected: str) -> bool:
    return sha256_digest(data) == expected.lower()


# ── Key management ──────────────────────────────────────────────────


def _load_trusted() -> dict:
    if TRUSTED_FILE.exists():
        return json.loads(TRUSTED_FILE.read_text())
    return {}


def _save_trusted(keys: dict):
    TRUSTED_FILE.parent.mkdir(parents=True, exist_ok=True)
    TRUSTED_FILE.write_text(json.dumps(keys, indent=2))


def import_key(key_path: str) -> dict:
    """Import a PGP public key file. Returns {'fingerprint': ..., 'keyid': ...}."""
    gpg = _gpg()
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
    trusted = _load_trusted()
    result = []
    for k in gpg.list_keys():
        fp = k["fingerprint"]
        result.append({
            "keyid": k["keyid"],
            "fingerprint": fp,
            "uids": k["uids"],
            "trusted": fp in trusted and trusted[fp].get("trusted", False),
        })
    return result


def trust_key(fingerprint: str) -> bool:
    """Mark a key as trusted for signature verification."""
    gpg = _gpg()
    trusted = _load_trusted()
    if fingerprint not in trusted:
        # Try to find in the keyring
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


# ── Signature verification ─────────────────────────────────────────


def verify_signature(data: bytes, signature_asc: str) -> str | None:
    """Verify a detached PGP signature.

    Returns the signer's fingerprint on success, or None if verification fails.
    """
    gpg = _gpg()
    verified = gpg.verify_data(signature_asc, data)
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
