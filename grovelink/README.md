# GroveLink Phone

In-game phone HUD. Photos taken in GTA show up on your real phone (same Wi-Fi) via the local bridge on port **8088**.

Crash-safer CLEO: no `hold_cellphone`, no custom GXT `033E` draws. Labels use `0ACD` / `0ACE`. INBOX / STATUS read `link.ini`.

## One-click (beginners)

1. From the **repo root**, right-click **`INSTALL.bat`** → **Run as administrator**.
2. Wait for the green SUCCESS screen.
3. Desktop → **GroveLink Phone** → launch GTA → **K** → Camera → **Enter** / **Space**.

INSTALL finds GTA, copies support files, compiles with Sanny when available, creates Gallery folders, opens firewall **8088**, and places Desktop shortcuts + **`VERIFY_GROVELINK.bat`** + **`UPDATE_GROVELINK.bat`** + **`GroveLink_README.txt`** (same 3 steps + link to TROUBLESHOOTING) + `GroveLink_PHONE_URL.txt`. If Sanny is missing it prints exact F7 steps and **keeps** any existing `.cs`.

Double-click **VERIFY_GROVELINK.bat** (Desktop or repo root) anytime for an OK/MISSING checklist: `gta_sa.exe`, CLEO, `GroveLinkPhone.cs`, `link.ini`, Python, `config.ini`, `GroveLinkPhone.txt`, writable `bridge/photos`, firewall note, and the URLs to try.


## Already installed? Update in one click

Double-click Desktop (or repo-root) **`UPDATE_GROVELINK.bat`**. It downloads the latest zip from GitHub (no Git), overlays your install, and re-runs **INSTALL.bat**. See root README + [TROUBLESHOOTING.md](TROUBLESHOOTING.md) → **Updating / outdated version**.

Until PR #1 merges, `update.ini` defaults to branch `fix/grovelink-camera-snapshots` so the patcher gets this camera work; after merge set `branch=main`.

## In GTA

- **K** — open / close the phone
- **Up / Down** — menu wraps: **CAMERA / INBOX / CONTACTS / STATUS / HELP / CLOSE**
- **Enter** or **Space** — select / snap (Camera), read INBOX, cycle contacts, show status, show HELP
- **Backspace** — close
- **CAMERA** — snap; shutter sound (`018C`); shows **PHOTO TAKEN #N** (count from `link.ini`)
- **INBOX** — shows last SMS from the real-phone page (`INBOX.msg`); clears `INBOX.new`; plays a short sound (`018C`) when `new=1`
- **CONTACTS** — flavor only: cycles Sweet / Smoke / Ryder / Cesar lines via `0ACD` (static text, no ped models)
- **STATUS** — **BRIDGE LIVE** / **NO BRIDGE** + shot count from `link.ini` when readable
- **HELP** — K / Camera tips, **OPEN START GROVELINK ON PC**, and **Outdated? UPDATE_GROVELINK**
- **CLOSE** — put the phone away
- If the bridge is not running (`STATUS.bridge=0`), opening the phone reminds you once: **START GROVELINK BRIDGE**

## Bridge page (phone / PC browser)

- Header shows prominent **VERSION** + **PHOTOS** stats, **LIVE** pulse badge, **LAN** + **localhost** URLs, last poll time, unread count
- If `/api` fails: red banner **Bridge offline — run START_GROVELINK** (reconnects automatically when the bridge is back)
- **Copy** buttons for URLs; large **tap-to-copy IP:port** block + `sms:` note (no QR library); **`GET /qr`** share page with the same
- **Download latest** opens newest `/photo/…`; **Export zip** downloads `GET /export.zip` (bridge/photos only); **Mark all read** clears NEW badges
- **All / Today** album tabs (pure JS filter by photo `mtime`)
- Quick-reply chips: **Where you at?**, **Nice shot**, **Come to Grove** → fill + `POST /send`
- Meta line shows timestamp, **file size**, and filename
- **Delete** on each shot removes it from **bridge/photos only** — it does **not** delete the file in the GTA Gallery
- `server.max_photos` (default **40**) — bridge prunes oldest files under `bridge/photos` only
- Unread badge: shots newer than your last visit (`localStorage` timestamp) get a **NEW** highlight
- Meta `theme-color` + short **Add to Home Screen** tip for phones
- Empty state checklist if no photos yet
- Tap a shot to enlarge (lightbox) or open **/photo/…** full size
- Newest first with human-readable timestamps
- Auto-refresh interval from `server.poll_ms` (default **2000** ms), exposed in `/api` as `poll_ms`
- SMS box still posts to `/send` → `link.ini` INBOX for the in-game phone
- First load of `/` logs **Phone page opened** in the bridge window
- **`GET /api`** → JSON with `photos` (incl. `size` / `size_h`), `latest`, `count` / `photo_count`, `bridge_ok`, URLs, `max_photos`, `poll_ms`, `version`, refresh time
- **`GET /health`** → JSON `{ok, bridge_ok, photo_count, count, latest, galleries, ip, port, gta_dir, version, poll_ms, max_photos}`
- **`GET /export.zip`** → zip of current `bridge/photos` (stdlib `zipfile`; Gallery untouched)
- **`POST /delete`** (or careful `GET /delete?file=…`) → remove from bridge cache only
- On start: writes `bridge/OPEN_ON_PHONE.txt`, sets `STATUS.bridge=1`, optional browser open (`server.open_browser=1` default)
- After shutter (`PHOTO.take=1`), gallery is polled aggressively for a few seconds

## Manual install (advanced)

1. Compile `GroveLinkPhone.txt` → `[GTA SA]\CLEO\GroveLinkPhone.cs` (Sanny F7)
2. Copy `GroveLink.fxt` → `[GTA SA]\CLEO\GroveLink.fxt`
3. Copy `GroveLink/link.ini` → `[GTA SA]\CLEO\GroveLink\link.ini`
4. Ensure Gallery exists under Documents `GTA San Andreas User Files\Gallery`
5. Edit `bridge/config.ini` (`gta_dir`, gallery paths, `port=8088`, `open_browser=1`, `max_photos=40`, `poll_ms=2000`)
6. Run `bridge/START_GROVELINK.bat` (needs Python 2.7 / 3.4–3.8 stdlib)
7. Open the printed URL on the real phone (same Wi-Fi); allow firewall TCP 8088
8. Optional: copy repo-root `VERIFY_GROVELINK.bat` to Desktop for one-click checks

## Note on prebuilt `.cs`

`prebuilt/GroveLinkPhone.cs.b64` is an **OLD** minimal test stub (not the camera phone). Prefer compiling `GroveLinkPhone.txt` (INSTALL or Sanny F7). A full `.cs` is not produced on Linux CI.

## Feature checklist

See [FEATURES.md](FEATURES.md) for the full install / camera / inbox / phone-page list.

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
