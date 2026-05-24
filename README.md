# PanCalc Tools

Package manager, file converter, and developer toolkit for **Casio Prizm** calculators
(fx-CG50, fx-CG100, and compatible models).

Part of the [Pan Devs](https://github.com/pan-devs) project.

---

## 📖 Quick Start (for everyone)

> **PanCalc Tools** lets you install programs (add-ins) on your Casio calculator,
> convert photos and documents so you can view them on the calculator screen,
> and much more.

### 1. Install Python

PanCalc Tools needs **Python 3.10 or newer**.

#### 🐧 Linux

Open a **terminal** (search for "Terminal" in your apps) and type:

```bash
python3 --version
```

If you see `Python 3.10` or higher, you're ready. If not, install Python:

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

#### 🍎 macOS

1. Go to [python.org](https://www.python.org/downloads/) and download the latest
   **Python 3** installer.
2. Open the downloaded file and follow the steps.
3. Open the **Terminal** app (search with Cmd+Space).
4. Type `python3 --version` to confirm it's installed.

#### 🪟 Windows

1. Go to [python.org](https://www.python.org/downloads/) and download the latest
   **Python 3** installer.
2. **Important:** when installing, say "y" to everything when the terminal opens (do not freak out, it is save), specially the **"Add Python to PATH"**.
3. Open the **Command Prompt** (search "cmd" in the Start menu).
4. Type `python --version` to confirm it's installed.

### 2. Install PanCalc Tools

> **Nota:** El paquete aún no está en PyPI. Se instala directamente desde GitHub.

#### 🐧 Linux

Open a **terminal** and run:

```bash
cd ~
git clone https://github.com/pan-devs/pancalc-tools.git
cd pancalc-tools
pip install -e .
```

> If you get a "pip not found" error, use `pip3` instead:
> ```bash
> pip3 install -e .
> ```

> **⚠️  Error "externally-managed-environment"?**  Linux moderno bloquea `pip install`
> fuera de un entorno virtual. Soluciones:
> - **Opción A (recomendada):** `pip install --user -e .`
> - **Opción B (entorno virtual):**
>   ```bash
>   python3 -m venv .venv
>   source .venv/bin/activate
>   pip install -e .
>   ```
>   A partir de ahí usa `source .venv/bin/activate` antes de ejecutar `pcalc` y
>   `cd ~/pancalc-tools` para estar en el directorio del proyecto.
>
> Windows y macOS **no** tienen esta restricción.

#### 🍎 macOS

Open the **Terminal** app (Cmd+Space, type "Terminal") and run:

```bash
cd ~
git clone https://github.com/pan-devs/pancalc-tools.git
cd pancalc-tools
pip3 install -e .
```

#### 🪟 Windows

1. Descarga el ZIP desde
   [github.com/pan-devs/pancalc-tools](https://github.com/pan-devs/pancalc-tools)
   y extraelo en una carpeta (ej. `C:\pancalc-tools`).

2. Abre el **Command Prompt** (Inicio → "cmd") y escribe:

```cmd
cd C:\pancalc-tools
pip install -e .
```

> Si `pip` no se reconoce, instalaste Python sin marcar **"Add Python to PATH"**.
> Re-ejecuta el instalador de Python y marca esa casilla.

### 3. Connect your calculator

#### 🐧 Linux

1. Turn on your Casio calculator.
2. Press **F1** (USB mass storage mode).
3. Connect it with a USB cable.
4. The program will detect it automatically. If not, it will ask for your
   password to install `udisksctl` (needed for auto-mount).

#### 🍎 macOS

1. Turn on your Casio calculator.
2. Press **F1** (USB mass storage mode).
3. Connect it with a USB cable.
4. It should appear as a drive on your desktop and in **Finder**.
   The program will find it automatically.

#### 🪟 Windows

1. Turn on your Casio calculator.
2. Press **F1** (USB mass storage mode).
3. Connect it with a USB cable.
4. It should appear as a new drive in **File Explorer** (e.g. `D:\` or `E:\`).
   The program will find it automatically.

### 4. Launch the program

#### 🐧 Linux

In the **terminal**, type:

```bash
pcalc
```

The interactive menu will open.

#### 🍎 macOS

In the **Terminal** app, type:

```bash
pcalc
```

The interactive menu will open.

#### 🪟 Windows

In the **Command Prompt**, type:

```bash
pcalc
```

The interactive menu will open.

> 💡 **Tips:**
> - Use your mouse/trackpad and click to interact.
> - Find games at https://github.com/wavonzip/bdesretro/tree/main (with .nes).
> - To understand the code or doubts, ask this chatbot https://deepwiki.com/pan-devs/pancalc-tools
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

### From PyPI (coming soon)

```bash
pip install pancalc-tools
```

Until then, see [Quick Start](#-quick-start-for-everyone) for installation from GitHub.

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
