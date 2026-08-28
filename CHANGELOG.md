# Changelog

All notable changes to PanCalc Tools are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

## [0.2.4] - TBD

### Added
- **Local Library**: Import/remove local add-ins & games (`pcalc local import/remove/list`)
- **Games / Emulator Support**: NES, GB, GBA, SMS, GG ROMs via Nesizm/GPSP/SMSPlusGX
- **Games TUI Screen**: Install/Remove/Verify games alongside addins
- **Orphan Detection**: Remove screen scans calculator recursively for files not in registry (`[O]` badge)
- **Save File Cleanup**: Remove deletes `.sav/.srm/.state/.sgm/.frz` companion files
- **Format Validation**: Import warns on unexpected extensions with opt-in override (`--yes`)
- **Registry Unified View**: `[addin]` / `[emulator:emu/platform]` labels, game details
- **🗑️ Remove Local button**: Delete local library items from TUI
- **CI/CD**: `workflow_dispatch` for branch selection (dev/main)
- **Trash Undo**: dropping an item on the Trash bin now shows a snackbar with an **UNDO** action. Restores local convert files, calculator/device files (plus their companion save/state files) and local-library items. `_show_snackbar` gained optional `action_text`/`action_cb`; `_on_trash_drop_inner` captures a snapshot (`_snap_file`/`_snap_save_companions`/`_snap_library`) before deleting; `_undo_trash` restores it and `library.restore()` re-creates a removed entry + file.

### Changed
- License: Author changed to "Pan Devs" for privacy
- `.g3a` removed from game extensions (addins only: `.g3a`, `.g3e`)
- Games = emulator ROMs only (`.nes`, `.rom`, `.bin`, `.gba`, `.sms`, `.gg`)
- GnuPG: standalone GnuPG component (not Gpg4win) on Windows
- Files imported to library are **copied** to `~/.local/share/pancalc/library/files/`
- Library `remove()` deletes entry + physical file in `files/`
- GUI: card hover now zooms (scale 1.08) + rounded drop shadow, without changing card size or adding colors
- GUI: cards now use a fixed size (registry 320×145, converted/input 200×167) so dragged cards keep the same size instead of adapting
- GUI: every drop zone (Convert sections, Install target, Trash) now answers back with a 3-stage progressive feedback — idle → hover (colored border + soft glow) → armed (intense glow + copy-shift badge "Copy N to …") — so users get clear signals before the drop
- GUI: drop-zone content without its own size (install target, trash) now fills and centres within the drop zone, so the overlay + glow stay within the real bounds of the zone instead of sprawling across empty space
- GUI: Install target is now compact and centred (no longer full-width), in very light blue (`#BBDEFB`/`#90CAF9` on `#E3F2FD`) and the hover/armed glow is ultra-diffuse (HOVER blur 28 alpha 0.06, ARMED blur 40 alpha 0.10, spread 0, faint interior tint 0.03-0.04) so it barely bleeds past the zone
- GUI: Convert batch processing now shows a live progress panel over each drop zone — determinate ring + big percentage + estimated time left on the left, and a scrolling "terminal" log on the right that lists each generated file (`✓ foto.g3p`). Converted cards appear in real time as the batch runs, no view switch required.
- Convert: the percentage now also advances **within a single file** when a document/tall image produces many outputs (`.g3p` strips from image splits or PDF/DOCX pages, `.txt` pages). `converter` functions (`convert_image`, `convert_document_g3p`, `convert_text`) accept an optional `on_progress(done, total)` callback; the GUI marshals it thread-safely onto the event loop to update the ring/percentage live in all three zones (Fotos, Texto, BOTH).
- GUI: multi-selecting input/converted cards in Convert and then dragging one dims (opacity 0.3) the other selected cards — same behaviour as the addin/registry cards. Convert cards register in `_card_refs` (keyed by path) and share the `_on_selection_drag_start/_complete` handlers, which now also consider `_multi_selected`.
- GUI: the Trash zone now covers the **whole sidebar** instead of just the small icon at the bottom. The `NavigationRail` + trash visual become the `content` of a full-height `DropZone` (`expand=True`), so dragging any item onto the bar — no matter where (over the labels/Settings) — arms the delete state. The rail remains tappable. The zone uses a **bright red** glow/border/badge (`#FF3B30`) so it clearly reads as a delete/trash area instead of the unified brown `GLOW_COLOR`.
- Convert view now follows the same pattern as Games/Install: the per-card **Push checkboxes**, the **Select All/Deselect All** toggle and the **Delete Selected** button were removed. Instead there is a compact **"Drop here to Push"** zone (`_build_push_target`, like `_build_install_target`) at the bottom of the Convert view. Long-press a converted card to select it (highlighted border), then drop it on the Push zone to copy the converted g3p/txt to the calculator `pthings/`, or on the Trash to delete it (with UNDO) — the Trash now handles all deletion.
- Push is resolved from the **dropped cards' paths**, not the global selection; `_on_push_accept` filters `all_paths` to only existing `converted` `.g3p`/`.txt` files, so leftovers selected in other views (registry/games/installed) are never pushed. `_push_files(paths=None)` now accepts explicit paths (falls back to the legacy set when omitted).
- Removed `_build_checkbox`/`_toggle_push_selection` (gui_views) and `_delete_converted_selection` (gui) which became unused.
- GUI: dropping on the **Push zone** now asks for confirmation **"Push N file(s) to calculator?"** before copying (same confirmation pattern as Install, timed before looking up the calculator). Controlled by the new `confirm_push` config (default **on**, like dark mode), with a matching **"Confirm before pushing"** switch in Settings > Behavior.
- Trash: deleting **converted/convert_input** cards now also asks **"Delete N converted file(s)?"** before removing them (it previously deleted instantly). It shares the existing `confirm_remove` setting so it stays consistent with the rest of the Trash.
- GUI: removed the **`✅`/`❌` emoji prefixes** from success/error snackbars and status text (`"Installed …"`, `"Verify … OK/FAILED"`, `"name → fotos/textos"`, `"N file(s) pushed and deleted"`). Snackbars/banners already show a native Flet icon per type (`CHECK_CIRCLE` for success, `ERROR` for error), and the calculator-detected/not-detected view already shows a large native check/cross — the emojis were redundant. Also cleaned the `✅ Trusted`/`❌ Untrusted` text in the key-management view. Minimalist native indicators only.

### Fixed
- GUI: Convert no longer rebuilds the whole view after **every** file (which reset the overlay to 0% and made it look broken/cut off). `_convert_single` no longer calls `_build_current_view`; the batch refreshes once at the end and updates the overlay + grid live instead.
- GUI: Convert progress %/logs weren't visible live because the CPU-bound conversion (GIL-bound encoder) starved the UI thread before Flet could flush each update. The batch loop now does `await asyncio.sleep(0.02)` after each `overlay.update()`, so the determinate ring %, ETA and the per-file log lines render to the client between files.
- Trash drop: dropping a non-removable item left the zone stuck lit up (ARMED). The `DropZone` reset now always runs to idle before the injected drop logic, and the decorative overlay/badge no longer swallow the drop event.
- Trash/delete: a **single** local-lib item or local ROM dragged to the trash was silently ignored (only worked after multi-selecting). The registry card (gui_views) `/` Games card only attached `all_ids`/`all_lib_types` in selection mode, but `_on_trash_drop_inner` needs `all_ids` to delete & snapshot a library item. Single-item drag now always carries its own `all_ids=[id]`/`all_lib_types` (both the registry card and the Games card), so individual local items can be trashed+undone exactly like a multi-selection.
- Trash/delete: after a muti-selection delete, surviving (non-deleted) table/registry items could keep rendering with the leftover "selected" border even though they weren't really selected anymore (cosmetic desync). `_on_trash_drop_inner` now always clears `_selected_registry_ids` and `_multi_selected` after a trash action, so no residual selection is ever painted.
- GUI: drop-zone glow/border/badge with an alpha component rendered **brown/washed-out, never the intended colour** (reported repeatedly as "rojo que se ve marrón/oliva"). Root cause: `DropZone._with_alpha` appended the alpha as `#RRGGBBAA`, but Flet/Flutter parses hex as `#AARRGGBB`, so the leading ``#FF3B301A`` was read as R=`0x3B` G=`0x30` B=`0x1A` → a desaturated brown. Now emits `#AARRGGBB` (e.g. `#FF3B30` @0.10 → `#1AFF3B30`), so transparent glows are the correct hue (verified via X11 pixel-capture analysis).
- Verify for local games: `Path("").name` → empty string crash (LOGSTOREAD.md)
- Remove fallback: used addins-only registry, now includes games
- Boolean expression bug: `and/or` short-circuit pushed first file to `invalid` list
- GUI: pushing with **no calculator connected** now shows the same warning snackbar ("No calculator connected") as Addins/Games/Install — it previously used a different error notification with a different message.

## [0.2.3] - 2026-05-25

### Added
- Initial release
- Add-in management: install, remove, verify from pan-devs/pancalc-registry
- SHA256 + PGP signature verification (auto-downloaded Pan Devs key)
- File conversion: images/documents → `.g3p` format, `.txt` extraction
- Push converted files to calculator `pthings/` directory
- Calculator filesystem browser (Catch view)
- Terminal UI (Textual) with sidebar navigation
- CLI (click) with full command set
- Registry cache with 6-hour TTL
- GPG key management (import, trust, list, untrust)
- Windows installer (Inno Setup) with GnuPG bundle
- Automatic calculator detection on Linux/macOS/Windows
- Eject with safe unmount
