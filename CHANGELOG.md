# Changelog

## 9 — tools, incoming ring, live status

- Home menu adds **TOOLS** (Grove GPS waypoint, next radio station)
- Browser **RING** button opens an incoming-call screen in-game (Enter answer / Backspace decline)
- Status strip shows game clock + a wanted pip
- Controller/keyboard rumble on new SMS and incoming ring
- Chat page: quick chips, RING, live header
- `link.ini` INBOX `kind=0` text / `kind=1` call

## 8 — usable handset + missed-update tools

- Phone HUD redrawn: bezel, speaker grill, LCD, signal bars, battery, home button, SELECT/BACK soft keys
- In-call screen stays on screen for the whole call (name + ON CALL + hang up)
- Calls no longer freeze the script — ring and voice tick in the background so the phone keeps drawing
- Backspace hangs up a live call
- Defined missing `FORCE_CLOSE` (death / undefined player no longer jumps into nowhere)
- Text draw is turned off when the phone closes
- Highlight bar lines up with menu rows
- `CHECK.bat` compares installed vs pack version and patches if you missed an update
- `INSTALL.bat` / `PATCH.bat` find Steam and Rockstar Launcher folders
- Desktop launchers now point at the real `grovelink\bridge` folder (v7 desktop copy was broken)
- Patch no longer wipes `link.ini` mid-conversation
- Docs: INSTALL, PHONE, TROUBLESHOOT

## 7 — auto patch + phone HUD

- `INSTALL.bat` and `PATCH.bat` find GTA, copy assets, compile with Sanny if present, write version, open firewall 8088
- `UPDATE.bat` git-pulls this repo when Git exists, then patches
- Phone shell redrawn (bezel, LCD, signal bars, home button)
- In-call screen no longer flashes the reply list
- Docs in `docs/`

## 6 — calls + two-way texts

- Real SCRIPT SFX voice banks for Sweet, Smoke, Ryder, Cesar, OG Loc, Kendl
- Browser chat at port 8088; CJ replies from MESSAGES presets
- Incoming SMS pager in-game
