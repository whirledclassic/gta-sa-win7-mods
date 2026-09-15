# GroveLink — current features

Pack version: see root **`VERSION`**. Crash-safer CLEO (no `hold_cellphone`, no custom GXT `033E`). Bridge is **stdlib-only** (Win7 Python 2.7 / 3.4–3.8).

## Install / update / verify

| Feature | How |
|--------|-----|
| **One-click install** | Root `INSTALL.bat` (Run as admin) — finds GTA, copies fxt/ini, compiles with Sanny when found, Gallery folders, firewall TCP **8088**, Desktop starters |
| **One-click update** | Desktop / repo `UPDATE_GROVELINK.bat` — GitHub zip (no Git), overlays files, re-runs INSTALL |
| **Health check** | Desktop / repo `VERIFY_GROVELINK.bat` — OK/MISSING for game, CLEO, `.cs`, `link.ini`, Python, config, photos dir, URLs |
| **Desktop starters** | **GroveLink Phone**, `START_GROVELINK`, `VERIFY_GROVELINK`, `UPDATE_GROVELINK`, `GroveLink_README.txt`, `GroveLink_PHONE_URL.txt`, `GroveLink_REPO.txt` (not INSTALL itself) |

## In-game phone (CLEO)

| Menu | Behavior |
|------|----------|
| **CAMERA** | Snap (Enter/Space); shutter sound; `PHOTO.take` + count; **PHOTO TAKEN #N** |
| **INBOX** | Shows last SMS from phone page; clears `INBOX.new`; sound when new |
| **CONTACTS** | Cycles Sweet / Smoke / Ryder / Cesar flavor lines (static text) |
| **STATUS** | **BRIDGE LIVE** / **NO BRIDGE** + shot count from `link.ini` |
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
| **Export zip** | `GET /export.zip` — zip of `bridge/photos` only (+ button on page) |
| **Album tabs** | All / Today (mtime filter in pure JS) |
| **Quick replies** | Chips → `POST /send` |
| **Delete** | Removes bridge cache copy only (not GTA Gallery); remembered in `photos_deleted.txt` |
| **Download latest** | Opens newest `/photo/…` |
| **Share** | Tap-to-copy IP:port, `sms:` note, `GET /qr` (no QR library) |
| **Unread / NEW** | `localStorage` last-visit badges; Mark all read |
| **Prune** | `server.max_photos` (default 40) — oldest under `bridge/photos` only |
| **Poll interval** | `server.poll_ms` (default **2000**) exposed to the page via `/api` |
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
