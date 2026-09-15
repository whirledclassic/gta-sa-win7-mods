# GroveLink — current features

Pack version: see root **`VERSION`** (`1.5.0`). Crash-safer CLEO (no `hold_cellphone`, no custom GXT `033E`). Bridge is **stdlib-only** (Win7 Python 2.7 / 3.4–3.8).

## Install / update / verify / test

| Feature | How |
|--------|-----|
| **One-click install** | Root `INSTALL.bat` (Run as admin) — finds GTA, copies fxt/ini, compiles with Sanny when found, Gallery folders, firewall TCP **8088**, Desktop starters |
| **One-click update** | Desktop / repo `UPDATE_GROVELINK.bat` — GitHub zip (no Git), overlays files, re-runs INSTALL |
| **Health check** | Desktop / repo `VERIFY_GROVELINK.bat` — OK/MISSING for game, CLEO, `.cs`, `link.ini`, Python, config, photos dir, URLs |
| **Smoke test** | `tests/smoke_bridge.py` (Linux/Win7, stdlib) or `grovelink/bridge/TEST_BRIDGE.bat` — asserts `/health`, `/api`, `/export.zip`, HTML, CLEO static |
| **Desktop starters** | **GroveLink Phone**, `START_GROVELINK`, `VERIFY_GROVELINK`, `UPDATE_GROVELINK`, `GroveLink_README.txt`, `GroveLink_PHONE_URL.txt`, `GroveLink_REPO.txt` (not INSTALL itself) |
| **START bat** | Prints pack **VERSION**; if Python missing, clear Win7 3.8.10 instructions + opens python.org download page |

## In-game phone (CLEO)

| Menu | Behavior |
|------|----------|
| **CAMERA** | Snap (Enter/Space); shutter sound; `PHOTO.take` + count; **PHOTO TAKEN #N** |
| **INBOX** | Shows SMS when `new=1`; otherwise **NO NEW TEXTS**; sound when new |
| **CONTACTS** | Cycles Sweet / Smoke / Ryder / Cesar flavor lines (static text) |
| **STATUS** | **LIVE N  PHONE PAGE ON PC** / **NO BRIDGE** + shot count from `link.ini` |
| **HELP** | K / Camera tips, START GROVELINK on PC, **UPDATE_GROVELINK** if outdated |
| **CLOSE** | Put phone away |
| Keys | **K** toggle · Up/Down wrap · Enter/Space select · Backspace close |
| Bridge-down | Once per open: **START GROVELINK BRIDGE** if `STATUS.bridge=0` |

## Bridge / phone page tools

| Feature | Detail |
|--------|--------|
| **Live indicator** | Green pulsing **LIVE** badge when `/api` polls succeed; dim **OFF** + banner when offline |
| **Reconnect banner** | “Bridge offline — run START_GROVELINK” if `/api` fails / times out |
| **Version + photo count** | Prominent stats on the page header (also in `/api` + `/health`) |
| **Empty-state LAN IP** | First visit with no photos: **large LAN IP:port** (tap to copy) + checklist; header Copy buttons kept |
| **Delete confirm** | Pinch-friendly modal **“Delete this shot?”** (big Cancel / Delete) — SA green theme; bridge cache only |
| **Filename search** | Search box filters the feed by photo filename (client-side) |
| **Clear all phone copies** | Button + `POST /clear` (or `GET /clear?confirm=1`) — wipes `bridge/photos` only after confirm |
| **Export zip** | `GET /export.zip` — zip of `bridge/photos` only (+ button on page) |
| **Album tabs** | All / Today (mtime filter in pure JS) |
| **Quick replies** | Chips → `POST /send` |
| **Delete** | Removes bridge cache copy only (not GTA Gallery); remembered in `photos_deleted.txt` |
| **Download latest** | Opens newest `/photo/…` |
| **Share** | Tap-to-copy IP:port, `sms:` note, `GET /qr` (no QR library) |
| **Unread / NEW** | `localStorage` last-visit badges; Mark all read |
| **Prune** | `server.max_photos` (default 40) — oldest under `bridge/photos` only |
| **Poll interval** | `server.poll_ms` (default **2000**) exposed to the page via `/api` |
| **last_error** | `/api` + `/health` include `last_error` when Gallery / bridge photos are unreadable (empty string when OK) |
| **Shutter burst** | After `PHOTO.take=1`, aggressive Gallery poll for a few seconds |
| **Gallery watch** | Re-detects Gallery dirs every second |
| **Endpoints** | `/`, `/api`, `/health`, `/send`, `/delete`, `/photo/…`, `/qr`, `/export.zip` |

## Config (`grovelink/bridge/config.ini`)

```ini
[server]
host = 0.0.0.0
port = 8088
open_browser = 1
max_photos = 40
poll_ms = 2000
```

Paths: `gta_dir`, `gallery_dir`, `gallery_dir_alt` (INSTALL overwrites these).

## Mission Switcher (optional)

Beginners: install **SkinOnly** only (`MissionSwitcher_SkinOnly`) — safer on story missions. See [switcher/README.md](../switcher/README.md).
