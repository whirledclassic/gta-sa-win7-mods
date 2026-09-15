# GroveLink — current features

Pack version: see root **`VERSION`** (`1.8.2`). Crash-safer CLEO (no `hold_cellphone`, no custom GXT `033E`). Bridge is **stdlib-only** (Win7 Python 2.7 / 3.4–3.8).

## Install / update / verify / test

| Feature | How |
|--------|-----|
| **One-click install** | Root `INSTALL.bat` (Run as admin) — finds GTA, copies fxt/ini, compiles with Sanny when found, Gallery folders, firewall TCP **8088**, Desktop starters |
| **CLEO.asi missing** | Big red warning + **https://cleo.li** link; pause before continuing (support files still copy) |
| **One-click update** | Desktop / repo `UPDATE_GROVELINK.bat` — GitHub zip (no Git), overlays files, re-runs INSTALL |
| **Health check** | Desktop / repo `VERIFY_GROVELINK.bat` — OK/MISSING for game, CLEO, `.cs`, `link.ini`, Python, config, photos dir, **VERSION** (prints pack version), URLs |
| **Human changelog** | Root `CHANGELOG.md` — pack 1.0→current highlights |
| **Smoke test** | `tests/smoke_bridge.py` (Linux/Win7, stdlib) or `grovelink/bridge/TEST_BRIDGE.bat` — asserts `/health`, `/api`, `/news`, `/send`, `/export.zip`, HTML gallery, CLEO static |
| **Desktop starters** | **GroveLink Phone**, `START_GROVELINK`, `VERIFY_GROVELINK`, `UPDATE_GROVELINK`, `GroveLink_README.txt`, `GroveLink_PHONE_URL.txt`, `GroveLink_REPO.txt` (not INSTALL itself) |
| **START bat** | Prints pack **VERSION** (CR-stripped); if Python missing, clear Win7 3.8.10 instructions + opens python.org download page |
| **Port in use** | Bridge prints plain English **port N busy** if TCP bind fails (close other GroveLink / free the port) |

## In-game phone (CLEO)

| Menu | Behavior |
|------|----------|
| **CAMERA** | Snap (Enter/Space); shutter sound; `PHOTO.take` + count; **PHOTO TAKEN #N**. **Gallery only — never writes NEWS keys / never files Herald** |
| **INBOX** | Shows SMS when `new=1`; otherwise **NO NEW TEXTS**; sound when new |
| **NEWS** | **Separate feature:** snap + `PHOTO.take` + count + `NEWS.make=1` + **`NEWS.zone` location tag** → bridge files Herald with 📍 badge; shows **BREAKING NEWS SNAP** |
| **Closed-phone SMS** | If `INBOX.new=1`, once: **SMS FROM REAL PHONE** (0ACD + sound) so you open **K** |
| **NEWS toast** | If `NEWS.new=1` (after NEWS menu or web Breaking News): **NEWS FILED** once, then clears flag |
| **CONTACTS** | Cycles Sweet / Smoke / Ryder / Cesar / **Catalina** flavor lines (static text; advances each select) |
| **STATUS** | **LIVE N  PHONE PAGE ON PC** / **NO BRIDGE** + shot count from `link.ini` |
| **HELP** | Camera = pics to phone only; NEWS = snap + Herald; START GROVELINK; **UPDATE_GROVELINK** if outdated |
| **CLOSE** | Put phone away |
| Keys | **K** toggle · Up/Down wrap (0–6: CAMERA/INBOX/NEWS/CONTACTS/STATUS/HELP/CLOSE) · Enter/Space select · Backspace close |
| Bridge-down | Once per open: **START GROVELINK BRIDGE** if `STATUS.bridge=0` |

## Bridge / phone page tools

| Feature | Detail |
|--------|--------|
| **Live indicator** | Green pulsing **LIVE** badge when `/api` polls succeed; dim **OFF** + banner when offline |
| **Reconnect banner** | “Bridge offline — run START_GROVELINK” if `/api` fails / times out |
| **Version + photo count** | Prominent stats on the page header (also in `/api` + `/health`) |
| **Empty-state LAN IP** | First visit with no photos: **large LAN IP:port** (tap to copy) + checklist; header Copy buttons kept |
| **Sort toggle** | **Newest / Oldest** tab — **client-side only** (server `/api` always newest-first) |
| **Help / shortcuts footer** | Compact footer: `?` toggles detail, `Esc` closes lightbox/confirm, `/` focuses search; GTA key reminders |
| **Empty actions disabled** | **Clear all**, **Export zip**, and **Download latest** disabled (dimmed) when photo count is 0 |
| **Hidden / skipped note** | If delete skip list non-empty: shows **Hidden from phone: N** (`skipped_deleted` in `/api` + `/health`) |
| **Delete confirm** | Pinch-friendly modal **“Delete this shot?”** (big Cancel / Delete) — SA green theme; bridge cache only |
| **Filename search** | Search box filters the feed by photo filename (client-side) |
| **Clear all phone copies** | Button + `POST /clear` / `GET /clear?confirm=1` — **confirm required** on both; wipes `bridge/photos` only |
| **Export zip** | `GET /export.zip` — zip of `bridge/photos` only (+ button on page) |
| **Album tabs** | All / Today (mtime filter in pure JS) |
| **Quick replies** | Chips → `POST /send` |
| **Delete** | Removes bridge cache copy only (not GTA Gallery); remembered in `photos_deleted.txt` |
| **Download latest** | Opens newest `/photo/…` |
| **Share** | Tap-to-copy IP:port, `sms:` note, `GET /qr` (no QR library) |
| **Favicon-free** | No favicon; `apple-mobile-web-app-capable` + **Add to Home Screen** tip |
| **Unread / NEW** | `localStorage` last-visit badges; Mark all read |
| **Prune** | `server.max_photos` (default 40) — oldest under `bridge/photos` only |
| **Poll interval** | `server.poll_ms` (default **2000**) exposed to the page via `/api` |
| **last_error** | `/api` + `/health` include `last_error` when Gallery / bridge photos are unreadable (empty string when OK) |
| **Shutter burst** | After `PHOTO.take=1` or `NEWS.make=1`, aggressive Gallery poll; **only** `NEWS.make` then creates Herald (Camera never does) |
| **Gallery watch** | Re-detects Gallery dirs every second |
| **Endpoints** | `/`, `/api`, `/api/chat`, `/health`, `/send`, `/caption`, `/news`, `/news/<id>`, `/delete`, `/clear`, `/photo/…`, `/qr`, `/export.zip` |

## Config (`grovelink/bridge/config.ini`)

```ini
[server]
host = 0.0.0.0
port = 8088
open_browser = 1
max_photos = 40
poll_ms = 2000
```

**Camera ≠ Breaking News:** there is **no** `news.auto` (removed in 1.8.1). Camera snaps stay on the phone page; use CLEO **NEWS** or the web **Breaking News** button for Herald articles.

Paths: `gta_dir`, `gallery_dir`, `gallery_dir_alt` (INSTALL overwrites these).

## Mission Switcher (optional)

Beginners: install **SkinOnly** only (`MissionSwitcher_SkinOnly`) — safer on story missions. See [switcher/README.md](../switcher/README.md).
