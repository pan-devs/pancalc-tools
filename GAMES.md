# Games / Emulators — User Guide

Play retro games on your Casio fx-CG50 via emulators installed from the registry.

---

## Supported Platforms

| Platform          | Extensions                     | Emulator        | Status   |
|-------------------|--------------------------------|-----------------|----------|
| NES               | `.nes`                         | Nesizm          | ✅ Ready |
| Game Boy / Color  | `.gb`, `.gbc`                  | GPSP*           | ⏳ Soon  |
| Game Boy Advance  | `.gba`                         | GPSP*           | ⏳ Soon  |
| Master System     | `.sms`                         | SMSPlusGX*      | ⏳ Soon  |
| Game Gear         | `.gg`                          | SMSPlusGX*      | ⏳ Soon  |
| Generic ROM       | `.rom`, `.bin`                 | Platform-dependent | —     |

\* Emulator add-in not yet available in the registry — check back later.

> **Candidate**: a Game Boy Advance emulator port (`gpsp-sh4-jit`, by
> KaraRyougi) has been identified for the fx-CG50/fx-CG100. It is **not** part
> of the registry yet — it still needs review and signing by Pan Devs. No date
> is promised; follow the registry for updates.

## ROM Policy & Responsibility

- PanCalc Tools and the **registry do not host or distribute copyrighted ROMs**.
  The only hosted entry is a small mock/test file used to demonstrate the
  registry architecture (`test_rom` — **do not download it**, it is not a game).
- **You are responsible** for the game files you add, install, and play. Only
  use ROMs you own, that are freely licensed, or whose copyright holder has
  authorised distribution (e.g. homebrew, public-domain, or openly licensed
  games). Please support the original creators.
- Games you add locally stay on your machine; PanCalc Tools only ever transfers
  files you explicitly choose to install on your calculator.

## Installing an Emulator

1. Go to **Install** screen (TUI) or run:

```bash
pcalc install nesizm
```

2. This installs the NES emulator to your calculator

## Adding Games

### Via TUI

1. Go to **Games** screen
2. Click **"📁 Add Game File"**
3. Select one or more `.nes`, `.gba`, `.rom`, `.bin`, `.sms`, `.gg` files
4. They appear in the list with `[L]` (local) badge

### Via CLI

```bash
pcalc games import supermario.nes              # import to library
pcalc games install test_rom                    # install by registry ID
pcalc games remove supermario                   # remove from library
```

## Installing Games to Calculator

- In **Games** screen, check the games you want (they must be installed on your calculator to play)
- Click **"📥 Install Checked Games"**
- The ROM is copied to the calculator

## Playing

1. On your calculator, open the emulator (e.g. **Nesizm**)
2. Navigate to the game file
3. Play

## Save Files

- Emulators create save files next to the ROM:
  - `.sav` — standard save
  - `.srm` — battery-backed save
  - `.state` — emulator state snapshot
  - `.sgm` / `.frz` — additional save formats
- When you **remove** a game from the calculator via PanCalc Tools, these are deleted too
- **To backup saves**: copy them off the calculator before removing

## Registry Games

Games in the official registry include metadata (only a mock/test entry is
hosted — see [ROM Policy](#rom-policy--responsibility)):

```json
{
  "emulator": "nesizm",
  "platform": "NES",
  "filename": "test.nes"
}
```

The **Registry** view in TUI marks them as `[emulator:nesizm/NES]`.

## Notes

- Some games are `.g3a` files that bundle the ROM inside the add-in — these are
  **addins**, not games. They appear in the **Install** screen, not Games.
- Games / Emulators screen is for **ROM files** (`.nes`, `.gba`, etc.) that
  are loaded by an emulator at runtime.
