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

### Fixed
- Trash drop: dropping a non-removable item left the zone stuck lit up (ARMED). The `DropZone` reset now always runs to idle before the injected drop logic, and the decorative overlay/badge no longer swallow the drop event.
- Verify for local games: `Path("").name` → empty string crash (LOGSTOREAD.md)
- Remove fallback: used addins-only registry, now includes games
- Boolean expression bug: `and/or` short-circuit pushed first file to `invalid` list

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
