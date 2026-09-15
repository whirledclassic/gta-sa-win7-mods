# GroveLink Phone

In-game phone HUD on the right of the screen. Photos taken in GTA show up on your real phone (same Wi-Fi) via the local bridge on port **8088**.

Crash-safer script: no `hold_cellphone`, no custom GXT `033E` draws. Menu labels use `0ACD` highpriority text.

## In GTA

- **K** — open / close the phone
- **Up / Down** — menu (CAMERA / INBOX / CLOSE labels appear)
- **Enter** or **Space** — select / snap (Camera)
- **Backspace** — close

## Install (one-click)

Prefer root **`INSTALL.bat`** (Run as administrator). It:

1. Copies `GroveLink.fxt` and `GroveLink\link.ini` into `[GTA]\CLEO\`
2. Compiles `GroveLinkPhone.txt` → `GroveLinkPhone.cs` when Sanny is found
3. Creates `%USERPROFILE%\Documents\GTA San Andreas User Files\Gallery`
4. Writes `bridge\config.ini` with gallery paths
5. Opens firewall TCP 8088
6. Places `START_GROVELINK.bat` on the Desktop

If Sanny is missing, compile once yourself (F7) and copy the `.cs` into `[GTA]\CLEO\`. INSTALL will not wipe an existing `.cs` just because compile was skipped.

## Manual install (single files)

1. Compile `GroveLinkPhone.txt` → `[GTA SA]\CLEO\GroveLinkPhone.cs`
2. Copy `GroveLink.fxt` → `[GTA SA]\CLEO\GroveLink.fxt`
3. Copy `GroveLink/link.ini` → `[GTA SA]\CLEO\GroveLink\link.ini`
4. Run `bridge/START_GROVELINK.bat`
5. Open the printed URL on the real phone

## Verify camera snapshots

1. Run the bridge; leave the window open.
2. PC: **http://127.0.0.1:8088** — phone: **http://LAN:8088**
3. In GTA: **K** → Camera → **Enter** or **Space**
4. Expect the shot on the page within a couple of seconds (`/` and `/api`)

The bridge re-detects Gallery folders every second, so photos still appear even if the Gallery directory did not exist when the bridge started.

## Note on prebuilt `.cs`

This repo may ship a tiny prebuilt test blob under `prebuilt/`. That is **not** the full camera phone. Prefer compiling `GroveLinkPhone.txt` (INSTALL or Sanny F7). A full `.cs` binary is not produced on Linux CI.
