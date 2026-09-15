# GroveLink troubleshooting (Windows 7)

## Quick health check

Double-click **`VERIFY_GROVELINK.bat`** (Desktop after INSTALL, or repo root). It prints **OK** / **MISSING** for:

- `gta_sa.exe`, `CLEO.asi`, `GroveLinkPhone.cs`, `link.ini`
- Python, `config.ini`, bridge script
- `GroveLinkPhone.txt` in the repo + writable `bridge/photos`
- Firewall note + URLs to try (`http://127.0.0.1:8088`, `/health`, `/qr`, `/export.zip`, phone LAN URL)

Fix anything marked MISSING, then run VERIFY again.


## Updating / outdated version

### One-click patch (preferred)

1. Double-click Desktop **`UPDATE_GROVELINK.bat`** (or the copy next to `INSTALL.bat` in your zip/repo folder).
2. Accept Administrator if asked.
3. Wait for **SUCCESS — Updated to version X**.
4. Start GroveLink → Launch GTA → **K** Camera.

The updater:
- Reads `update.ini` (`branch=…`, optional `release=latest`) or env `UPDATE_BRANCH`
- Downloads a GitHub zip with Win7-safe PowerShell `WebClient` (bitsadmin fallback) — **no Git**
- Unzips with Shell.Application COM (no `Expand-Archive` required)
- Copies files over your existing install (uses `GroveLink_REPO.txt` if the bat is on the Desktop)
- Re-runs **INSTALL.bat** so CLEO / firewall / Desktop shortcuts refresh

Pack version: root **`VERSION`** file; also on the phone page header and **`/health`** → `version`.

**Note:** While PR #1 is open, `update.ini` defaults to `branch=fix/grovelink-camera-snapshots` so beginners get the camera fixes before merge. After merge, edit `update.ini` to `branch=main`.

### Offline / download failed — manual zip

If **UPDATE_GROVELINK.bat** fails, it prints an **EXACT browser URL** (copy/paste) plus: Extract All → open folder with `INSTALL.bat` → Run as administrator. Your current install path is also printed.

1. On any PC with internet, download:
   - Current PR branch: https://github.com/whirledclassic/gta-sa-win7-mods/archive/refs/heads/fix/grovelink-camera-snapshots.zip  
   - After merge: https://github.com/whirledclassic/gta-sa-win7-mods/archive/refs/heads/main.zip
2. Copy the zip to the Win7 PC (USB is fine).
3. Extract (right-click → Extract All).
4. Run **`INSTALL.bat`** as administrator from the new folder.
5. Optional: replace your old folder, or keep using the new extract path (INSTALL writes a fresh `GroveLink_REPO.txt` on the Desktop).

If unzip inside the updater fails: delete `%TEMP%\GroveLinkUpdate` and retry, or use the manual steps above.

## No `GroveLinkPhone.cs` after install

INSTALL only replaces the `.cs` when Sanny successfully compiles a new one. It never deletes a working script without a replacement.

1. Install **Sanny Builder 3 or 4**: https://sannybuilder.com  
2. Open `grovelink\GroveLinkPhone.txt`  
3. Press **F7** (Compile)  
4. Copy `GroveLinkPhone.cs` into `[GTA]\CLEO\`  
5. Confirm CLEO is installed (`CLEO.asi` next to `gta_sa.exe`) and `IniFiles.cleo` is in the CLEO folder  
   (INSTALL shows a **big red CLEO.asi missing** screen with https://cleo.li if it is absent)  

Do **not** decode `prebuilt/GroveLinkPhone.cs.b64` for the camera phone — that blob is an old “GROVELINK OK” stub only.

## Bridge finds no gallery

Expected folder (INSTALL creates it):

`%USERPROFILE%\Documents\GTA San Andreas User Files\Gallery`

Also checked: `My Documents\...`, Public Documents, and paths in `bridge\config.ini`.

- Leave the bridge running; it **re-detects galleries every second** and creates missing folders when it can.  
- Take one in-game photo (K → Camera → Enter/Space) so GTA writes into Gallery.  
- Edit `bridge\config.ini` `[paths] gallery_dir=` if your user files live elsewhere.  
- Check `/health` → `galleries` array.

## Phone can’t connect (Wi-Fi / firewall / IP)

1. PC and phone on the **same Wi-Fi** (not guest/VPN isolation).  
2. Bridge window must stay open; Desktop **GroveLink Phone** / START_GROVELINK.  
3. On the PC try **http://127.0.0.1:8088** first.  
4. On the phone use **http://LAN-IP:8088** printed by the bridge (also `bridge\OPEN_ON_PHONE.txt` and Desktop `GroveLink_PHONE_URL.txt`).  
5. INSTALL adds firewall rule **GroveLink Phone** TCP **8088**. If you skipped admin install, allow Python/port 8088 manually.  
6. `/health` should return JSON with `"ok": true`. VERIFY_GROVELINK also reminds you about the firewall.

## Photo taken but blank page

1. Confirm in-game **PHOTO TAKEN #N** (count bumping).  
2. Confirm `cleo\GroveLink\link.ini` has `PHOTO.take` briefly flip to `1` (bridge clears it).  
3. Bridge burst-polls Gallery for a few seconds after shutter — wait ~2–4s and refresh.  
4. Check Gallery folder for new `.jpg` / `.bmp` files larger than ~100 bytes.  
5. `/api` should list `photos` with `file` + `when`, plus `latest` and `count`.  
6. If Gallery path is wrong, fix `config.ini` and restart the bridge.

## Delete on phone page vs GTA Gallery

**Delete** on the web page only removes the copy under `grovelink\bridge\photos\`. It does **not** delete the original in Documents `...\Gallery`. GTA's own gallery is untouched.

Deleted names are remembered in `bridge\photos_deleted.txt` so the watcher does not immediately re-copy the same shot from Gallery while you still want it hidden on the phone page.

## Too many bridge photos / prune

`config.ini` → `[server] max_photos = 40` (default). The bridge keeps at most that many files under `bridge\photos` and **deletes the oldest bridge copies** when over the limit. Gallery originals are never pruned.

## Phone page tips (Live, offline banner, export, poll)

- **LIVE** green pulse means `/api` succeeded recently; if the bridge dies, a red banner says **Bridge offline — run START_GROVELINK** until it comes back.
- Header **VERSION** / **PHOTOS** stats match `/api` + root `VERSION`.
- **Export zip** / `GET /export.zip` downloads current `bridge/photos` only (not GTA Gallery).
- Refresh interval: `config.ini` → `server.poll_ms = 2000` (ms). The page reads `poll_ms` from `/api`.
- **All / Today** tabs filter by photo modified time (Today = since local midnight).
- Quick-reply chips (**Where you at?**, **Nice shot**, **Come to Grove**) fill the SMS box and `POST /send`.
- Large **tap-to-copy IP:port** block (and **`/qr`**) — no QR code library; use `sms:` link or copy into your phone browser on the same Wi-Fi.
- Meta line shows timestamp + **file size**.
- Bridge console prints **Phone page opened** the first time someone loads `/`.


## Sanny F7 steps

1. Open Sanny Builder → set game to **San Andreas** if asked.  
2. File → Open `GroveLinkPhone.txt` (needs `{$USE ini}` / `{$USE CLEO}` — already in the file).  
3. **F7** Compile. Fix any opcode/plugin errors (IniFiles.cleo / CLEO must match).  
4. Output `.cs` → copy to `[GTA]\CLEO\GroveLinkPhone.cs`.

Menu after compile: **CAMERA / INBOX / CONTACTS / STATUS / HELP / CLOSE** (Up/Down wrap, K toggle). **HELP** shows tips + START GROVELINK + **UPDATE_GROVELINK**. **STATUS** shows **BRIDGE LIVE** / **NO BRIDGE** + shot count. Camera snap plays a short shutter sound (`018C`).

Mission Switcher (optional): compile **one** of `switcher\MissionSwitcher_SkinOnly.txt` (safer) or `MissionSwitcher.txt`, copy `.cs` to CLEO. INSTALL auto-compiles SkinOnly when Sanny is found (SUCCESS mentions it only if installed).

## Win7 Python versions

Bridge is **stdlib only** (no pip packages).

| Version | Notes |
|--------|--------|
| **Python 3.8.10** | Recommended on Windows 7 |
| **Python 2.7.18** | Supported |
| 3.4–3.7 | Usually fine if stdlib `http.server` works |
| 3.9+ | May not install/run cleanly on stock Win7 |

`START_GROVELINK.bat` tries `python`, `py -3`, `py -2`, then common install paths.

## SMS / INBOX not showing in GTA

1. Bridge must be running (`STATUS.bridge=1` in `link.ini`).  
2. Send from the web page SEND box.  
3. In GTA: **K** → **INBOX** → Enter/Space — shows `INBOX.msg`, clears `INBOX.new`, plays a short sound when the message was new. Or tap a quick-reply chip on the phone page.

## STATUS says NO BRIDGE (or page says offline)

1. Start Desktop **GroveLink Phone** / START_GROVELINK and keep the window open.  
2. Bridge sets `STATUS.bridge=1` on start (and `0` on clean stop).  
3. In GTA: **K** → **STATUS** → should read **BRIDGE LIVE  N shots**.  
4. On the phone page: red banner clears automatically once `/api` responds again.
