# Orphan Removal — User Guide

Remove files from your calculator that are **not in the official Pan Devs registry**.

---

## What are Orphans?

Any file on the calculator with a known add-in or game extension that **doesn't match**
any entry in the Pan Devs registry:

| Extension set | Extensions                        | Icon |
|---------------|-----------------------------------|------|
| Addins        | `.g3a`, `.g3e`                    | 📦   |
| Games         | `.nes`, `.rom`, `.bin`, `.gba`, `.sms`, `.gg` | 🎮   |

Common sources of orphan files:
- Manually copied ROMs or add-ins
- Old/unlisted add-ins from before the registry
- Games installed with other tools
- Test or development files

## How Orphan Detection Works

1. Go to **Remove** screen in the TUI (or run `pcalc remove`)
2. PanCalc Tools **recursively scans** the entire calculator
3. Each file is checked against the registry via `_match_addin_by_filename`
4. Files that **match** → shown with their registry name and 📦/🎮 icon
5. Files that **don't match** → shown with `[O]` badge and icon by type

## Removing Orphans

### Via TUI

1. Check the orphan items (or any items you want to remove)
2. Click **"🗑️ Remove Checked"**
3. All checked items — addins, games, and orphans — are removed at once

### Via CLI

```bash
pcalc remove                         # interactive selection
pcalc rm <relative-path>             # remove by path
pcalc rm pthings/fotos/photo.g3p     # specific file
```

## What Gets Deleted

For each orphan file removed:
- The main ROM or add-in file
- **Companion save files** with the same name stem:
  - `.sav`, `.srm`, `.state`, `.sgm`, `.frz`
  - Case-insensitive match in the same directory
  - Appended extension (e.g. `game.nes` → `game.nes.sav`)

Other files in the calculator are never touched.

## Safety

- Only files with known extensions (addin or game) are listed
- Files in `pthings/fotos/`, `pthings/textos/`, `pthings/` root are shown
  separately and can be removed with the same button
- Registry-matched items use the official `remove()` which tracks in `installed.json`
- Orphans use direct filesystem deletion — no local database is affected
