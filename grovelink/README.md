# GroveLink Phone

In-game phone HUD. Photos taken in GTA show up on your real phone (same Wi-Fi) via the local bridge on port **8088**.

Crash-safer CLEO: no `hold_cellphone`, no custom GXT `033E` draws. Labels use `0ACD` / `0ACE`. INBOX reads `link.ini`.

## One-click (beginners)

1. From the **repo root**, right-click **`INSTALL.bat`** → **Run as administrator**.
2. Wait for the green SUCCESS screen.
3. Desktop → **GroveLink Phone** → launch GTA → **K** → Camera → **Enter** / **Space**.

INSTALL finds GTA, copies support files, compiles with Sanny when available, creates Gallery folders, opens firewall **8088**, and places Desktop shortcuts + `GroveLink_PHONE_URL.txt`. If Sanny is missing it prints exact F7 steps and **keeps** any existing `.cs`.

## In GTA

- **K** — open / close the phone
- **Up / Down** — menu (CAMERA / INBOX / CLOSE)
- **Enter** or **Space** — select / snap (Camera) or read INBOX
- **Backspace** — close
- Camera snap shows **PHOTO TAKEN #N** (count from `link.ini`)
- If the bridge is not running (`STATUS.bridge=0`), opening the phone reminds you once: **START GROVELINK BRIDGE**
- INBOX shows the last SMS from the real-phone page (`INBOX.msg`); clears `INBOX.new` when read

## Bridge page (phone / PC browser)

- Header shows **LAN URL** + **localhost URL**, bridge online, last refresh time
- **Copy** buttons for URLs; large SEND / tap targets for mobile
- Empty state checklist if no photos yet
- Tap a shot to enlarge (lightbox) or open **/photo/…** full size
- Newest first with human-readable timestamps
- Auto-refresh about every 2 seconds (indicator in header)
- SMS box still posts to `/send` → `link.ini` INBOX for the in-game phone
- **`GET /health`** → JSON `{ok, photo_count, galleries, ip, port, gta_dir}`
- On start: writes `bridge/OPEN_ON_PHONE.txt`, sets `STATUS.bridge=1`, optional browser open (`server.open_browser=1` default)
- After shutter (`PHOTO.take=1`), gallery is polled aggressively for a few seconds

## Manual install (advanced)

1. Compile `GroveLinkPhone.txt` → `[GTA SA]\CLEO\GroveLinkPhone.cs` (Sanny F7)
2. Copy `GroveLink.fxt` → `[GTA SA]\CLEO\GroveLink.fxt`
3. Copy `GroveLink/link.ini` → `[GTA SA]\CLEO\GroveLink\link.ini`
4. Ensure Gallery exists under Documents `GTA San Andreas User Files\Gallery`
5. Edit `bridge/config.ini` (`gta_dir`, gallery paths, `port=8088`, `open_browser=1`)
6. Run `bridge/START_GROVELINK.bat` (needs Python 2.7 / 3.4–3.8 stdlib)
7. Open the printed URL on the real phone (same Wi-Fi); allow firewall TCP 8088

## Note on prebuilt `.cs`

`prebuilt/GroveLinkPhone.cs.b64` is an **OLD** minimal test stub (not the camera phone). Prefer compiling `GroveLinkPhone.txt` (INSTALL or Sanny F7). A full `.cs` is not produced on Linux CI.

## Troubleshooting

See [TROUBLESHOOTING.md](TROUBLESHOOTING.md).
