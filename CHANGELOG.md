# Changelog

All notable changes to PanCalc Tools are documented here.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)

## [0.3.9] - 2026-09-05

### Added
- **Real OCR for photos**: images (`.png`, `.jpg`, `.jpeg`, `.bmp`, …) dropped into the **Text** conversion target are now recognized with **RapidOCR** (ONNXRuntime, bundled models, fully offline) instead of producing an (almost) empty TXT. Works in the GUI and via `pcalc convert photo.jpg --ocr`.
- **Confidence filtering**: OCR lines below a confidence threshold (default `0.5`, adjustable via `ocr_min_confidence` in Settings/data or `--min-confidence` in the CLI) are **discarded** — the app never writes "invented" text from handwriting or low-quality images. The GUI reports *"OCR: N líneas · conf. media M%"* (and warns when nothing readable was found).
- **ASCII transliteration**: recognized text keeps PDF/DOCX behaviour — accents/`ñ` are stripped for calculator compatibility (`café` → `cafe`).

### Changed
- **OCR is optional**: the core package does not pull the (~60 MB) ONNX runtime; the Windows build bundles it via the new `[ocr]` extra. Installer grows to ≈150 MB.
- **New optional dependency group**: `pip install pancalc-tools[ocr]` adds the OCR engine.

## [0.3.8] - 2026-09-05

### Changed
- **Installed view — multi-file add-ins as one card**: an add-in spanning several files (e.g. KhiCAS with `g3a` + `ac2`) now renders as a **single card** in the Installed view instead of one entry per file. The header count *"add-ins · games"* reflects the number of cards (unique add-ins), not the number of files.
- **Installed view — orphan ROMs under Games**: orphan files on the calculator with ROM extensions (`.rom`, `.bin`, `.gba`, `.nes`, `.sms`, `.gg`) now show up in the **Games** column of the Installed view (with a game icon and counted as games), instead of being mixed into the Add-ins list.

### Fixed
- **Deleting a multi-file add-in**: dragging a multi-file add-in card (e.g. KhiCAS) to the trash now removes **all** of its files, not just a single one (the drag payload carries every file path).

## [0.3.7] - 2026-09-05

### Fixed
- **TUI worker lock-up**: starting an install/verify/convert operation with nothing selected (or without a calculator connected) could leave the app permanently blocked until restart. The "operation running" flag is now always cleared when a worker ends.
- **Partial multi-file installs**: `installed.json` is now persisted after each file is written. If a multi-file add-in fails mid-batch, the files already written are recorded (instead of leaving orphan files the app ignores).
- **PGP signature download**: the installer no longer downloads the same signature URL twice when the registry entry has no explicit `signature_url`; the default `<download_url>.asc` is only retried when it differs from the configured one.
- **Version source**: the app version no longer relies on `importlib.metadata`, which could report a stale or `0.0.0` value in dev / non-installed runs. `pcalc.__version__` is now a single literal source of truth (also picked up by `pyproject.toml` via a dynamic version), so the CLI, TUI and GUI always agree.
- **GUI background tasks**: fire-and-forget async tasks (scan, registry update, eject, self-update, background scanner) now surface exceptions to the debug log instead of silently dropping them.
- **GUI concurrent installs**: installing straight from an add-in detail dialog is now guarded against running two installations at the same time.
- **Debug log**: `debug_log` writes to the platform config directory instead of a hard-coded developer path.

### Changed
- **Updater**: `latest_release()` now returns `None` when a release has no matching installer asset, instead of treating the GitHub release page as a downloadable "installer".

## [0.3.6] - 2026-09-05

### Changed
- **License**: the project is now licensed under the **GNU Affero General Public License v3.0 (AGPL-3.0)**, replacing the previous "Pan Devs Non-Commercial Attribution License". This makes the project compatible with its AGPL-licensed dependency (PyMuPDF) and removes the non-commercial / no-AI-training restrictions.
- **Debug log**: `pcalc_debug.log` is no longer tracked by version control and is ignored via `.gitignore`.
- **Docs**: added `THIRD_PARTY_NOTICES.md` with licenses of all bundled third-party components (bundled with the installer too); `GAMES.md` documents the registry ROM policy and a candidate GBA emulator.

## [0.3.5] - 2026-09-03

### Fixed
- **Version shown in the app**: the window title, app bar, and Settings no longer report the stale or `0.0.0` package metadata version. They now read `version.txt` bundled with the build, so they reflect the actual release tag after updating.
- **Empty registry fallback**: when the add-in/games catalog is empty, the Registry and Games views now show a "downloading or not yet available — please wait, then click Refresh" message instead of a bare "no add-ins loaded".

### Changed
- **Self-update**: the update confirmation dialog now states that "the installation will start shortly after you close the app".

## [0.3.4] - 2026-09-03

### Changed
- **Self-update**: the update dialog now asks the user to close the app window to finish, and the installer is launched by a detached helper that waits for the app process to actually end (instead of relying on an unreliable programmatic window close / forced exit). The installer still starts automatically right after the app closes.

## [0.3.3] - 2026-09-03

### Changed
- **Settings**: moved the app version + repository link to the top of the Settings view.

## [0.3.2] - 2026-09-03

### Fixed
- **Uninstaller**: no longer crashes with a "cannot call 'ExecAsOriginalUser' function during Uninstall" runtime error. The real user's `%APPDATA%`/`%LOCALAPPDATA%` is now captured by the installer (where `ExecAsOriginalUser` is legal), persisted to `HKLM\Software\Pan Devs\PanCalc Tools`, and read back by the uninstaller so cleanup targets the correct profile even when elevated.
- **Self-update**: the app now reliably closes when confirming an update (hard exit moved to a dedicated thread so it cannot be skipped by the window teardown cancelling the async task); the installer wizard opens only after the app has exited.

### Changed
- **Download dialogs**: added "please be patient" guidance to the first-run registry download, the manual registry refresh, and the update download dialogs.
- **UI text**: remaining user-visible Spanish strings (drag feedback, file/photos/texts section labels) translated to English.

## [0.3.0] - 2026-09-03

### Changed
- **Update notice**: the new-version notification now shows only as the top banner (removed the duplicate snackbar)
- **Settings**: added a clickable link to the project repository (`github.com/pan-devs/pancalc-tools`)
- **Delete flow**: reverted the file-deletion progress dialogs to the previous direct delete logic (restoring reliable behavior when removing installed/calculator files)

## [0.2.9] - TBD

### Added
- **Installed view columns**: cards now split into three columns — Addins | Games (ROMs) | Pthings — each with its own header and updated total counts
- **App self-update**: checks GitHub Releases on launch (configurable in Settings) and shows a banner when a new version is available; the "Update" flow downloads the installer with a live progress bar and then launches it
- **Settings**: "Check for new app version on launch" toggle + "Check for Updates" button
- **Self-update over a running app**: the app now fully exits *before* the new installer is launched (detached delayed launch + `os._exit`), so the setup no longer reports it "cannot close the app"
- Installer closes a still-running `pancalc-tools-gui.exe` automatically (`CloseApplications` + named `AppMutex`) — also covers manual reinstalls
- **Stable AppId** (fixed GUID) so updating replaces the same install instead of creating a duplicate entry in Add or Remove Programs
- **Uninstaller options page**: choose what to remove before uninstalling —
  - "Remove everything installed by PanCalc Tools" (master box, checked by default)
  - Settings & configuration (`%APPDATA%\pancalc\pancalc`)
  - Data, cache, Local Library & GnuPG keys (`%LOCALAPPDATA%\pancalc\pancalc`)
  - Microsoft Visual C++ Redistributable (x64) — always offered but **not** covered by "Remove everything" and kept by default, since other programs may depend on it; silently uninstalled with `/uninstall /quiet` when chosen (a copy is bundled in `{app}\redist` for that purpose)
- Uninstaller force-removes runtime leftovers inside the app folder via `[UninstallDelete]`
- Silent uninstall (`/VERYSILENT`) stays fully clean: app + data + config are removed, VC++ Redistributable is kept
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
- **Packaging**: the Windows installer (`build-installer.yml` + `pancalc-tools.iss`) now ships **only the GUI** as the main product, fully self-contained. GnuPG is **bundled inside the app** (`<install>\gpg\bin\gpg.exe` resolved by `_bundled_gpg()` in `pcalc/crypto.py` first, falling back to `PATH`/Program Files) instead of being installed system-wide, and the CLI/TUI/PATH-in-registry shortcut options were removed from the installer. README restructured so end users only see the GUI install, with CLI/TUI/GnuPG documented at the end for developers running via pip (`pancalc-tools[gui]`).

### Fixed
- **Uninstaller options UX**: "Remove everything" is now a separate master checkbox that, when checked, greys out and locks the Settings/Data boxes (all removed); when unchecked, those become plain independent checkboxes you can tick one at a time (ticking just "cache" etc. actually works now)
- **Uninstaller on non-admin accounts**: with UAC elevation the data/config deletion now targets the *real* user's `%APPDATA%`/`%LOCALAPPDATA%` (resolved via `ExecAsOriginalUser`), so a full uninstall + fresh reinstall shows the first-run wizard again — previously it deleted the administrator profile's folders and left the user's data behind
- **Windows self-update**: the delayed installer launch no longer flashes a console window or errors with "Windows cannot find the file '\'" — it now spawns a hidden PowerShell helper (routing the setup path through an environment variable, single `CREATE_NO_WINDOW` flag) *before* tearing down the window, and a watchdog thread guarantees the app exits even if the window close handshake stalls, so it can never hang half-closed with a busy spinner
- **Uninstaller options**: the checkboxes are now siblings instead of a parent/child tree, so ticking one no longer ticks all the others (the "Remove everything" master box still toggles the settings/cache boxes, and Visual C++ always stays independent and unchecked by default)
- **Uninstaller**: the Visual C++ Redistributable description is no longer clipped to a single line — it now renders as a wrapping note above the list
- **Registry update** now shows a progress dialog (add-in catalog → game catalog → reload)
- **Verify** now shows a progress dialog while checking SHA-256 (it may download the source zip)
- **Installed cards** wrapped in `ft.Card()` so they show the Material surface instead of looking transparent
- Installed cards no longer have a per-card trash button — deletion is the global drag-to-trash (batch + undo)
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
