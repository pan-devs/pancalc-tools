# Local Library — User Guide

The Local Library lets you install add-ins and games **not in the official registry**.

---

## Overview

- Files imported are **copied** to `~/.local/share/pancalc/library/files/`
- Original file can be deleted after import — library has its own copy
- Each entry gets a unique ID, SHA256 hash, and metadata
- No PGP verification (you trust your own files / don't need the registry's key)
- SHA256 is still verified on install

## Supported Formats

| Type      | Extensions                         |
|-----------|------------------------------------|
| Add-ins   | `.g3a`, `.g3e`                     |
| Games     | `.nes`, `.rom`, `.bin`, `.gba`, `.sms`, `.gg` |

## How to Import

### Via TUI

1. Go to **Install** screen (for add-ins) or **Games** screen (for ROMs)
2. Click **"📁 Add Add-in File"** or **"📁 Add Game File"**
3. Select one or more files
4. If the extension is unexpected, you'll be asked to confirm

### Via CLI

```bash
pcalc local import myaddin.g3a               # add-in
pcalc local import game.nes                  # game ROM
pcalc local import --yes game.gba            # skip confirmation
```

### Completed

- The item appears in the **Install** / **Games** list with an `[L]` badge
- The original file can now be deleted — the copy in the library is what gets installed

## Listing Local Items

```bash
pcalc local list
```

In the TUI, local items are shown with an `[L]` marker and are merged into
the same list as official registry items.

## Removing from Library (not from calculator)

```bash
pcalc local remove <id>
```

In the TUI, select the items and click **"🗑️ Remove Local"**.

This deletes:
- The entry from `library.json`
- The copied file in `~/.local/share/pancalc/library/files/`

## Installing from Library

- Local items appear in **Install** / **Games** screens alongside official ones
- Select them and click **"📥 Install Checked"** or **"📥 Install Checked Games"**
- Install uses SHA256 verification — no PGP, since the file came from you
