# PanCalc Tools

Package manager, file converter, and developer toolkit for **Casio Prizm** calculators
(fx-CG50, fx-CG100, and compatible models).

Part of the [Pan Devs](https://github.com/pan-devs) project.

## Features

- **📦 Add-in management** — Install, remove, and verify add-ins from the
  [pan-devs/pancalc-registry](https://github.com/pan-devs/pancalc-registry)
  with automatic SHA256 + PGP signature verification.
- **🖼️ File conversion** — Convert images (PNG, JPG, BMP, GIF, TIFF, WebP) and
  documents (PDF, DOCX) to Casio `.g3p` photo format or plain text.
- **📤 Push to calculator** — Copy converted files to the calculator's `pthings/`
  directory (sorted into `fotos/` and `textos/` subdirectories).
- **🔍 Calculator browsing** — Browse the full calculator filesystem, identify
  known add-ins, and inspect storage usage.
- **🔐 Cryptographic verification** — SHA256 checksums on every download and
  PGP signature verification against the official Pan Devs key (auto-downloaded,
  no manual setup required).
- **🖥️ Dual interface** — Full-featured **Terminal UI** (Textual) and a
  complete **CLI** (click) for scripting.
- **🔑 PGP key management** — Import, trust, list, and untrust additional keys
  for advanced users.

## Installation

### Requirements

- **Python 3.10+**
- A **Casio Prizm** calculator connected via USB in **mass storage mode** (F1).

### From PyPI

```bash
pip install pancalc-tools
```

### From source

```bash
git clone https://github.com/pan-devs/pancalc-tools.git
cd pancalc-tools
pip install -e .
```

### Dependencies

| Package | Purpose |
|---------|---------|
| `click` | CLI framework |
| `rich`  | Terminal formatting & progress bars |
| `textual` | Terminal UI framework |
| `Pillow` | Image processing |
| `pymupdf` | PDF & DOCX parsing |
| `requests` | HTTP downloads |
| `python-gnupg` | PGP signature verification |
| `questionary` | Interactive prompts |
| `platformdirs` | Cross-platform config paths |

On **Windows**, install `pywin32` for drive detection:

```bash
pip install pancalc-tools[windows]
```

## Quick Start

### Terminal UI

```bash
pcalc
```

Opens the interactive TUI with a sidebar for navigation:

| Button | Action |
|--------|--------|
| 🏠 Home | Dashboard with calculator info & help |
| 📂 Catch | Browse calculator filesystem |
| 📥 Install | Install add-ins from the registry |
| 🗑️ Remove | Uninstall add-ins or delete `pthings/` files |
| 🔄 Convert | Convert images/documents to G3P/TXT |
| 📤 Push | Copy converted files to calculator |
| ✅ Verify | Check SHA256 of installed add-ins |
| 📋 Registry | Browse available add-ins |
| 🔑 PGP Keys | Manage cryptographic keys |
| 🔄 Update Registry | Force-refresh add-in list from GitHub |
| ⏏️ Eject | Safely unmount calculator |

### CLI

```bash
pcalc install khicas
pcalc verify
pcalc convert image.png
pcalc convpush
pcalc catch
pcalc eject
```

See all commands:

```bash
pcalc --help
```

## CLI Reference

### `pcalc list` / `search` / `info`

```bash
pcalc list                    # List all add-ins in the registry
pcalc search calculator       # Search by keyword
pcalc info khicas             # Show add-in details
```

### `pcalc install`

```bash
pcalc install khicas utilities   # Install multiple add-ins
pcalc install --yes khicas       # Skip confirmation prompts
pcalc install --overwrite khicas # Overwrite existing files
```

### `pcalc remove` / `rm`

```bash
pcalc remove khicas              # By add-in name
pcalc rm pthings/fotos/photo.g3p # By path (relative to mount)
```

### `pcalc verify`

```bash
pcalc verify                     # Verify ALL add-ins on the calculator
pcalc verify khicas utilities    # Verify specific add-ins
```

Scans the calculator directly — no local cache needed.

### `pcalc convert`

```bash
pcalc convert photo.png          # Image → G3P
pcalc convert doc.pdf            # PDF → interactive prompt (G3P/TXT/Both)
pcalc convert --g3p doc.pdf      # PDF → G3P only
pcalc convert --txt doc.pdf      # PDF → TXT only
pcalc convert --both doc.pdf     # PDF → G3P + TXT
```

### `pcalc convpush`

```bash
pcalc convpush                   # Copy all converted files to calculator
```

Files go to `pthings/fotos/` (`.g3p`) and `pthings/textos/` (`.txt`).
Filenames are automatically sanitized (accents stripped, spaces → `_`,
special characters removed).

### `pcalc catch` / `calc`

```bash
pcalc catch                  # Browse calculator filesystem
```

### `pcalc eject`

```bash
pcalc eject                   # Safely unmount calculator
```

### Registry

```bash
pcalc update-registry         # Force-refresh add-in registry from GitHub
```

### PGP Keys

```bash
pcalc import-key mykey.asc    # Import a PGP public key
pcalc list-keys               # List all keys and trust status
pcalc trust-key <fingerprint> # Trust a key for signature verification
pcalc untrust-key <fingerprint>
```

## Configuration

Settings are stored via `platformdirs` and can be managed programmatically:

| Key | Default | Description |
|-----|---------|-------------|
| `registry_url` | GitHub repo URL | Add-in registry source |
| `cache_ttl_hours` | 6 | Registry cache duration |
| `auto_update` | `true` | Auto-refresh registry on install |
| `confirm_install` | `true` | Ask before installing |
| `confirm_remove` | `true` | Ask before removing |

## Input / Output Layout

```
pancalc-tools/
├── convert/            ← Drop files here for conversion
│   ├── images/         (PNG, JPG, BMP, GIF, TIFF, WebP)
│   └── documents/      (PDF, DOCX)
├── converted/          ← Converted files appear here
│   ├── g3p/            (.g3p files)
│   └── txt/            (.txt files)
```

Both the TUI **Convert** and **Push** views scan these directories automatically.

## Security

### SHA256 Verification

Every add-in in the registry includes a `sha256` field. The installer computes
the SHA256 of every downloaded/extracted file and aborts on mismatch.

### PGP Signatures

All official registry files are signed with the **Pan Devs PGP key**.
The key is **auto-downloaded from the registry** on first use — no manual
import or trust setup required.

- Key fingerprint: `C7AD 9689 E894 B261 7EAB  CFE2 1A37 0E1B 68A1 94A8`
- Algorithm: Ed25519

For zip-type add-ins (e.g., Nesizm), verification downloads the zip,
extracts the `.g3a`, and computes the SHA of the extracted file —
no local cache dependency.

## Architecture

See [ARCHITECTURE.md](ARCHITECTURE.md) for a detailed overview of the codebase
structure, module responsibilities, and data flow.

## License

**PAN DEVS NON-COMMERCIAL ATTRIBUTION LICENSE v1.0**

- **Non-commercial use** is free with attribution required.
- **Commercial use** requires a separate paid license.
  Contact `pan.devs@proton.me`.
- **AI/ML training** on this code is explicitly prohibited.

See [LICENSE.md](LICENSE.md) for the full text.

## Contributing

Pull requests and issues are welcome. For major changes, please open an
issue first to discuss what you'd like to change.

### Development setup

```bash
git clone https://github.com/pan-devs/pancalc-tools.git
cd pancalc-tools
python -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## Links

- **Registry:** https://github.com/pan-devs/pancalc-registry
- **Issues:** https://github.com/pan-devs/pancalc-tools/issues
- **Contact:** pan.devs@proton.me
