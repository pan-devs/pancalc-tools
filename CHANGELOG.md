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

### Fixed
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
