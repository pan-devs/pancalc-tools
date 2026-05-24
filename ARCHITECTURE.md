# Architecture

## Overview

```
┌─────────────────────────────────────────────────────────────┐
│                      User Interface                         │
│  ┌─────────────────────┐    ┌─────────────────────────────┐ │
│  │   CLI (pcalc/cli.py) │    │  TUI (pcalc/tui.py)         │ │
│  │   click commands     │    │  Textual app + MainScreen   │ │
│  └──────────┬──────────┘    └──────────────┬──────────────┘ │
└─────────────┼──────────────────────────────┼────────────────┘
              │                              │
              ▼                              ▼
┌─────────────────────────────────────────────────────────────┐
│                     Core Modules                             │
│                                                              │
│  ┌──────────┐  ┌───────────┐  ┌───────────┐  ┌──────────┐  │
│  │installer │  │ converter │  │ calculator│  │  crypto  │  │
│  │ .py      │  │ .py       │  │ .py       │  │ .py      │  │
│  └────┬─────┘  └─────┬─────┘  └─────┬─────┘  └────┬─────┘  │
│       │              │              │              │        │
│       ▼              ▼              ▼              ▼        │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌──────────┐  │
│  │ registry │  │  Pillow   │  │  udisks  │  │python-   │  │
│  │ .py      │  │  pymupdf  │  │  (mount) │  │ gnupg    │  │
│  └──────────┘  └───────────┘  └──────────┘  └──────────┘  │
│                                                              │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐                  │
│  │  config  │  │   theme   │  │  banner  │                  │
│  │ .py      │  │ .py       │  │ .py      │                  │
│  └──────────┘  └───────────┘  └──────────┘                  │
└─────────────────────────────────────────────────────────────┘
```

## Package Structure

```
pcalc/
├── __init__.py      # Package metadata (version, author)
├── banner.py        # ASCII art banners & header printing
├── calculator.py    # Calculator detection & mounting
├── cli.py           # CLI commands (click) + AsciiBarColumn
├── config.py        # Persistent configuration
├── converter.py     # Image/Document → G3P/TXT conversion
├── crypto.py        # SHA256 hashing & PGP verification
├── installer.py     # Add-in install/remove/verify + filesystem walk
├── registry.py      # Add-in registry (fetch, cache, search)
├── theme.py         # Color/style constants
└── tui.py           # Textual Terminal UI
```

## Module Descriptions

### `pcalc/calculator.py` — Device Detection

Handles finding and mounting Casio Prizm calculators on Linux, macOS, and
Windows.

- **`Calculator`** dataclass: model name, mount path, storage stats.
- **`find_calculator()`** — scans all mounted volumes for Casio devices
  (case-insensitive FAT32 label check). Uses `udisksctl` for auto-mount
  on Linux.
- **`require_calculator()`** — like `find_calculator()` but raises
  `RuntimeError` if not found (for commands that must have a device).

**Candidate paths by platform:**

| Platform | Paths scanned |
|----------|---------------|
| Linux    | `/media/<user>/*`, `/run/media/<user>/*` |
| macOS    | `/Volumes/*` |
| Windows  | Drive letters A-Z via `win32api` |

### `pcalc/registry.py` — Add-in Registry

Fetches the add-in list from the
[pan-devs/pancalc-registry](https://github.com/pan-devs/pancalc-registry)
GitHub repository.

- **`get_registry(force=False)`** — returns `list[dict]`. Cached locally
  for 6 hours (configurable). Pass `force=True` to bypass cache.
- **`get_addin(name)`** — lookup by ID or name.
- **`search_registry(query)`** — case-insensitive full-text search across
  name, description, author, and category.

### `pcalc/installer.py` — Add-in Operations

The core add-in lifecycle: install, remove, verify, and filesystem scanning.

#### Data Structures

- **`DeviceFile`**: filename, path, size, matching addin (or None)
- **`CalcEntry`**: recursive tree node — name, relative path, size,
  is_dir, addin match, children

#### Filesystem Scanning

- **`scan_device()`** — flat scan of the calculator root (for top-level .g3a)
- **`walk_calc()`** — recursive walk, matches files against registry by
  filename, returns `CalcEntry` tree
- **`iter_calc_files()`** — flat iterator over all files in the tree
- **`count_calc_files()`** — total file count

#### Install Flow

```
registry addin dict
        │
        ▼
_get_addin_files()      → list of file_info dicts
        │
        ▼
_download_bytes()       → raw bytes (with progress callback)
        │
        ▼
verify_sha256()         → compare against registry sha256
        │
        ▼
verify_official_signature() → PGP verify via crypto module
        │
        ▼
_extract_g3a_from_zip() → if download_type == "zip"
        │
        ▼
_write_with_progress()  → chunked write to calculator + fsync
        │
        ▼
installed.json update   → local cache of installed add-ins
```

#### Verify Flow (no-cache)

```
registry addin dict
        │
        ▼
┌─── files[]? ────→ per-file sha256 from registry
│
└─── single-file?
     │
     ├── direct ──→ sha256 from registry root
     └── zip ─────→ download zip, extract, compute sha256 of extracted file
                         │
                         ▼
                   compare with file on calculator
```

### `pcalc/converter.py` — File Conversion

Converts images and documents to Casio `.g3p` format.

#### G3P Format Pipeline

```
Input (PNG/PDF/DOCX)
        │
        ▼
Resize + Letterbox (to 384×216 for fx-CG50)
        │
        ▼
Quantize (RGB565 or 3-bit palette)
        │
        ▼
DEFLATE compress + Obfuscate (bitwise NOT + nibble swap)
        │
        ▼
Build header (magic, metadata, image header)
        │
        ▼
.g3p file
```

#### Key Functions

| Function | Input → Output |
|----------|---------------|
| `convert_image()` | PNG/JPG/BMP/GIF/TIFF/WebP → `.g3p` |
| `convert_document_g3p()` | PDF/DOCX → multiple `.g3p` pages |
| `convert_text()` | PDF/DOCX → `.txt` (ASCII) |
| `decode_image()` | `.g3p` → PNG |

**Constants:**

- `RENDER_SCALE = 3.2` — supersampling factor for PDF/DOCX rendering
- `PAGE_WIDTH = 384`, `PAGE_HEIGHT = 216` — target display resolution
- Image splitting: tall photos are split into multiple `.g3p` pages

#### Text Extraction

`convert_text()` uses `_clean_text()` to:
1. Normalize Unicode (NFD)
2. Strip combining marks (accents)
3. Remove non-printable characters
4. Collapse whitespace

### `pcalc/crypto.py` — Cryptography

#### SHA256

- **`sha256_digest(data)`** — hex digest of bytes
- **`verify_sha256(data, expected)`** — compare digest against expected

#### PGP

Uses `python-gnupg` (not `pgpy` — broken on Python 3.14+).

- The **official Pan Devs key** is auto-downloaded from the registry
  on first use — no manual setup required.
- **`verify_official_signature(data, signature_text)`** — downloads the
  official key if needed, imports it, and verifies the signature.
- **Key management**: `import_key()`, `list_keys()`, `trust_key()`,
  `untrust_key()`.

**Known issue with GPG 2.4.9**: `verify_data()` causes `BrokenPipeError`.
The module uses `verify_file()` with `io.BytesIO` and tempfiles instead.

### `pcalc/cli.py` — Command-Line Interface

Built with [click](https://click.palletsprojects.com/). Entry point: `pcalc`.

#### Custom Widgets

- **`AsciiBarColumn`** — Rich progress column using only ASCII chars
  (`▓`/`░`) styled with `theme.SUCCESS`/`theme.PRIMARY`.

#### Command Groups

| Command | Module dependency |
|---------|-------------------|
| `list`, `search`, `info` | `registry` |
| `install` | `registry`, `installer`, `crypto` |
| `remove`, `rm` | `installer`, `calculator` |
| `verify` | `installer`, `calculator`, `registry` |
| `convert` | `converter` |
| `convpush` | `calculator`, `converter` |
| `catch`, `calc` | `installer`, `calculator`, `registry` |
| `eject` | `calculator` |
| `update-registry` | `registry` |
| `import-key`, `list-keys`, `trust-key`, `untrust-key` | `crypto` |

### `pcalc/tui.py` — Terminal UI

Built with [Textual](https://textual.textualize.io/).

#### Architecture

```
PanCalcApp (Textual App)
    │
    └── MainScreen
        ├── Sidebar (Vertical, width=28)
        │   ├── Title "PanCalc Tools"
        │   ├── Calculator status (✅ model / ❌ No calculator)
        │   ├── 11 navigation buttons
        │   ├── Eject + Update Registry buttons
        │   ├── Quit button
        │   └── Key hint
        └── Content Panel (Vertical, id="content-panel")
            └── (dynamically swapped per view)
```

#### Message Protocol

All blocking operations run in worker threads and communicate back to the
UI via Textual messages:

| Message | Purpose |
|---------|---------|
| `LogMessage` | Append text to the active RichLog |
| `OperationDone` | Worker finished (triggers `on_worker_state_changed`) |
| `PushDone` | Push completed, carries file list for post-push deletion |
| `ConvertDone` | Conversion completed, carries original paths for deletion |

#### Views

| View ID | Class | Description |
|---------|-------|-------------|
| `home` | — | Dashboard with ASCII banner, calc info, help |
| `catch` | — | Calculator filesystem tree |
| `install` | `InstallRow` + `ToggleRow` | Registry add-in selection + install |
| `remove` | `RemoveRow` | Installed add-ins + pthings/ files |
| `convert` | `ConvertRow` | convert/{images,documents} → G3P/TXT |
| `convpush` | `ConvertRow` | converted/{g3p,txt} → calculator push |
| `verify` | `VerifyRow` | Installed add-in SHA256 verification |
| `registry` | `ListView` + `RichLog` | Browse registry + detail view |
| `keys` | `RichLog` | PGP key listing |

#### Widget Classes

| Widget | Base | Purpose |
|--------|------|---------|
| `ToggleRow` | `Static` | Generic selectable row with checkbox toggle |
| `InstallRow` | `ToggleRow` | Add-in row with name, version, size |
| `RemoveRow` | `ToggleRow` | Add-in or pthings file row |
| `VerifyRow` | `ToggleRow` | Add-in verification row |
| `ConvertRow` | `ToggleRow` | Convert/push file row with type tag |

#### Dialogs

| Dialog | Purpose |
|--------|---------|
| `_EjectDialog` | Confirm before ejecting calculator |
| `ConfirmDialog` | Generic Yes/No confirmation |

#### Key Bindings

| Key | Action |
|-----|--------|
| `Ctrl+S` | Command palette |
| `Escape` | Return to Home |
| `↑/↓` | Navigate |
| `Space` | Toggle selection |

### `pcalc/config.py` — Configuration

Persistent configuration stored via `platformdirs` (JSON file).

### `pcalc/theme.py` — Visual Theme

Color and style constants used by both CLI (Rich) and TUI (Textual).

## Data Flow: End-to-End Scenarios

### Installing an Add-in

```
User clicks "Install" in TUI (or runs `pcalc install khicas`)
        │
        ▼
_show_install() → loads registry → shows InstallRow list
        │
        ▼
User selects add-ins → clicks "Install Checked"
        │
        ▼
_install_impl() [worker thread]
        │
        ├── find_calculator() → ensure device connected
        ├── install(addin, calc, progress_callback)
        │       ├── _get_addin_files(addin) → resolve file list
        │       ├── _download_bytes(dl_url) → download
        │       ├── verify_sha256(raw, sha256) → integrity check
        │       ├── verify_official_signature(raw, sig) → authenticity
        │       ├── _extract_g3a_from_zip(raw, zip_file) → if needed
        │       ├── _write_with_progress(dest, data) → copy to calc
        │       └── _save_installed(installed) → local cache
        │
        └── post_message(LogMessage) → UI updates
```

### Converting and Pushing a Photo

```
User drops photo.png into convert/images/
        │
        ▼
User clicks "Convert" → selects file → "→ G3P"
        │
        ▼
_convert_impl("g3p") [worker thread]
        │
        ├── Sanitize filename (accents → ASCII, spaces → _)
        ├── convert_image(input, output, bit_depth=16)
        │       ├── Pillow resize + letterbox
        │       ├── RGB565 quantization
        │       ├── DEFLATE compress + obfuscate
        │       └── Write .g3p to converted/g3p/
        ├── f.unlink() (delete original from convert/)
        │
        └── post_message(ConvertDone) → confirm delete originals?
        │
        ▼
User clicks "Push" → selects file → "Push Selected to Calculator"
        │
        ▼
_convpush_impl() [worker thread]
        │
        ├── Sanitize filename
        ├── Copy to pthings/fotos/ (or pthings/textos/ for .txt)
        │
        └── post_message(PushDone) → confirm delete from converted/?
```

## Error Handling

- All modules that interact with hardware/network raise `RuntimeError`.
- Both CLI and TUI catch `RuntimeError` and display user-friendly messages.
- The CLI exits with `SystemExit(1)` on failure to support `&&` chaining.
- The TUI shows errors in the active `RichLog` and via `notify()`.
- The `_worker_running` flag prevents concurrent operations in the TUI.

## Testing

Tests are in `tests/`. Run with:

```bash
python -m pytest tests/
```

## Key Technical Decisions

| Decision | Rationale |
|----------|-----------|
| `python-gnupg` over `pgpy` | `pgpy` 0.6.0 depends on `imghdr` (removed in Python 3.13+), broken on 3.14 |
| `verify_file()` over `verify_data()` | GPG 2.4.9 `BrokenPipeError` with `verify_data()` |
| `RENDER_SCALE=3.2` | High-quality supersampling for document → G3P |
| TUI containers via constructor args | Textual `MountError` when mounting after creation |
| `self.run_worker()` instead of `@work` | `@work` decorator not available in Textual 8.2.7 |
| Instance-ref button routing | Textual `DuplicateIds` error with reused button IDs |
