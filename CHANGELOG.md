# Changelog

## 10 — companion switcher v2

- H / G / J / R: become nearest, next companion, restore CJ, hard reset
- Original story ped is hidden instead of cloned or deleted
- Model-load timeout so the game cannot freeze on a missing DFF
- Auto-restore CJ if you die while switched
- Names on screen, 22 m scan, walkstyles for Kendl/Catalina
- Removed false matches on generic male models 1 and 2
- `docs/SWITCHER.md`

## 9 — tools, incoming ring, live status

- Home menu adds **TOOLS** (Grove GPS waypoint, next radio station)
- Browser **RING** button opens an incoming-call screen in-game (Enter answer / Backspace decline)
- Status strip shows game clock + a wanted pip
- Controller/keyboard rumble on new SMS and incoming ring
- Chat page: quick chips, RING, live header
- `link.ini` INBOX `kind=0` text / `kind=1` call

## 8 — usable handset + missed-update tools

- Phone HUD redrawn: bezel, speaker grill, LCD, signal bars, battery, home button, SELECT/BACK soft keys
- In-call screen stays on screen for the whole call
- Calls no longer freeze the script
- Backspace hangs up a live call
- Defined missing `FORCE_CLOSE`
- `CHECK.bat` compares installed vs pack version
- Desktop launchers point at the real bridge folder
- Patch no longer wipes `link.ini`

## 7 — auto patch + phone HUD

- INSTALL.bat / PATCH.bat find GTA, compile, firewall 8088
- UPDATE.bat git-pulls then patches

## 6 — calls + two-way texts

- Real SCRIPT SFX voice banks
- Browser chat at port 8088
