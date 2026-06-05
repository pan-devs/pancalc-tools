# PanCalc Tools

Package manager, file converter, and developer toolkit for **Casio Prizm** calculators
(fx-CG50, fx-CG100, and compatible models).

Part of the [Pan Devs](https://github.com/pan-devs) project.

---
[![Ask DeepWiki](https://deepwiki.com/badge.svg)](https://deepwiki.com/pan-devs/pancalc-tools)

## 📖 Quick Start (for Windows only)

Download the PanCalc-Tools-Setup-XX.XX.XX.exe file in the latest [release](https://github.com/pan-devs/pancalc-tools/releases) by clicking it to install PanCalc Tools.

Windows may not install it sying that it just protected you from the exe file, but click on the three dots in the download section, click on "conserve" (or something like that), then down in the "Eliminate" button click on the small arrow and click again on conserve. The installation should continue. 

Then, accept that it can change your settings/device (when the pop-up window appear, click "yes"), and continue the installation. 

It is highly recomended to click/select every box.

And no worries, it is safe.

[⬇️ Download Quick Install tutorial](https://github.com/pan-devs/pancalc-tools/raw/refs/heads/main/QuickInstall-Win-TUI-small.mp4)



> 💡 **Tips:**
> - Use your mouse/trackpad and click to interact.
> - Questions? Ask the specialiced AI at https://deepwiki.com/pan-devs/pancalc-tools
> - Press **Ctrl+S** to open the command palette.
> - Press **Esc** to return to the home screen.
> - Use **↑** and **↓** to move between items.
> - Press **Space** to select/deselect an item.

---

## Features

- **📦 Add-in management** — Install, remove, and verify add-ins from the
   [pan-devs/pancalc-registry](https://github.com/pan-devs/pancalc-registry)
   with automatic SHA256 + PGP signature verification.
- **🖼️ File conversion** — Convert images (PNG, JPG, BMP, GIF, TIFF, WebP) and
   documents (PDF, DOCX) to Casio `.g3p` photo format or plain text.
- **📤 Push to calculator** — Copy converted files to the calculator's `pthings/`
   directory (sorted into `fotos/` for .g3p images and `textos/` for .txt files).
- **🔍 Calculator browsing** — Browse the full calculator filesystem, identify
   known add-ins, and inspect storage usage.
- **🔐 Cryptographic verification** — SHA256 checksums on every download and
   PGP signature verification against the official Pan Devs key (auto-downloaded,
   no manual setup required).
- **🖥️ Dual interface** — Full-featured **Terminal UI** (Textual) and a
   complete **CLI** (click) for scripting.
- **🔑 PGP key management** — Import, trust, list, and untrust additional keys
   for advanced users.

> **📝 Filename Limitations:** The Casio calculator cannot read files with spaces or non-English characters (accents, special symbols) in their names. Files are automatically sanitized when pushed (spaces → _, accents removed, etc.).
> 
> **📄 TXT File Reading:** To view TXT files on your calculator, you need to install the "Utilities" add-in from the registry first. This add-in provides a file viewer for text documents on your Casio calculator (and also a JPEG viewer).
---



## Expanded start guide (for other OS and developers/advanced users)

### 1. Install dependencies

Before installing PanCalc Tools, you need a few things depending on your OS.

#### 🪟 Windows

**Python 3.10+**

1. Go to [python.org](https://www.python.org/downloads/) and download the latest **Python 3** installer.
2. **Important:** check the box **"Add Python to PATH"** at the bottom of the installer screen before clicking Install.
3. Open **Command Prompt** (search "cmd" in the Start menu).
4. Type `python --version` to confirm.

**Microsoft Visual C++ Redistributable** — needed for PDF/DOCX conversion (pymupdf):

- 64-bit (most users): https://aka.ms/vs/17/release/vc_redist.x64.exe
- 32-bit Python: https://aka.ms/vs/17/release/vc_redist.x86.exe

Download and install, then restart Command Prompt.

**Gpg4win** — needed for add-in signature verification:

1. Download from [gpg4win.org](https://gpg4win.org)
2. Run the installer (default options are fine).
3. Confirm it works: open Command Prompt and type `gpg --version`.

---

#### 🍎 macOS

**Python 3.10+**

1. Go to [python.org](https://www.python.org/downloads/) and download the latest **Python 3** installer.
2. Open the downloaded file and follow the steps.
3. Open the **Terminal** app (Cmd+Space → "Terminal").
4. Type `python3 --version` to confirm.

**Xcode Command Line Tools** — needed for some dependencies (pymupdf):

```bash
xcode-select --install
```

> If you see "already installed", you're good.

**GnuPG** — needed for add-in signature verification. Install one of:

- **GPG Suite** (recommended, includes GUI): [gpgtools.org](https://gpgtools.org)
- **Homebrew** (if you use it): `brew install gnupg`


---

#### 🐧 Linux

**Python 3.10+** — open a terminal and check:

```bash
python3 --version
```

If you see `Python 3.10` or higher, you're ready. If not:

- **Ubuntu / Debian / Mint:**
  ```bash
  sudo apt install python3 python3-pip
  ```
- **Arch / Manjaro:**
  ```bash
  sudo pacman -S python python-pip
  ```
- **Fedora:**
  ```bash
  sudo dnf install python3 python3-pip
  ```

**GnuPG** — needed for add-in signature verification. Check if it's installed:

```bash
gpg --version
```

If not found:

- **Ubuntu / Debian / Mint:** `sudo apt install gnupg`
- **Arch / Manjaro:** `sudo pacman -S gnupg`
- **Fedora:** `sudo dnf install gnupg2`


---

### 2. Install PanCalc Tools

Open a terminal (search for "cmd" in Windows) and run:

```bash
python -m pip install pancalc-tools
```

> On Linux/macOS, use `python3 -m pip` if `python` is not found.

**Windows only** — also install `pywin32` for automatic calculator eject:

```bash
python -m pip install "pancalc-tools[windows]"
```

> **Linux users:** if you get an `externally-managed-environment` error, use:
> ```bash
> python -m pip install --user pancalc-tools
> ```

---

### 3. Launch the program

Open a terminal (or Command Prompt on Windows) and type:

```bash
pcalc
```

The interactive menu will open.

> **⚠️ Windows — if `pcalc` is not recognized:**
> Python's Scripts directory may not be in your PATH.
> Add `%APPDATA%\Python\Python3xx\Scripts` to your PATH
> (replace `3xx` with your Python version, e.g. `Python314`),
> or use the fallback command:
> ```bash
> python -m pcalc
> ```

---

### 4. Connect your calculator

#### 🪟 Windows

1. Turn on your Casio calculator.
2. Press **F1** (USB mass storage mode).
3. Connect it with a USB cable.
4. It will appear as a new drive in **File Explorer** (e.g. `D:\` or `E:\`).
   PanCalc Tools will detect it automatically.

#### 🍎 macOS

1. Turn on your Casio calculator.
2. Press **F1** (USB mass storage mode).
3. Connect it with a USB cable.
4. It will appear as a drive in **Finder** and be detected automatically.

#### 🐧 Linux

1. Turn on your Casio calculator.
2. Press **F1** (USB mass storage mode).
3. Connect it with a USB cable.
4. PanCalc Tools will detect it automatically.

> If the calculator is not detected, try running `udisksctl mount -b /dev/sdb1`
> (replace `sdb1` with the correct device — check with `lsblk`).

---

After connecting your calculator, navigate to the **Catch** option in the
pcalc interface to browse its filesystem.


## Installation

### Requirements

- **Python 3.10+**
- A **Casio Prizm** calculator connected via USB in **mass storage mode** (F1).

### From PyPI

```bash
python -m pip install pancalc-tools
```

On **Windows**, also install `pywin32` for automatic drive detection and eject:

```bash
python -m pip install pancalc-tools[windows]
```

> **Note:** PGP signature verification requires `gpg` (GnuPG) installed on your system.
> See the Quick Start section above for installation instructions per OS.

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
