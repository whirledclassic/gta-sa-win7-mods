# GroveLink Phone

CJ uses a San Andreas cellphone: **real character voice lines**, on-screen contacts, and two-way texts with any browser on the same Wi-Fi.

## In GTA

- **K** pull out / put away (cellphone animation)
- **Up / Down** move the menu
- **Enter** select
- **Backspace** back / hang up

### Home
CONTACTS, MESSAGES, CAMERA, CLOSE

### Contacts (Enter = call)
Sweet, Smoke, Ryder, Cesar, OG Loc, Kendl

Calls play the **game’s own cellphone / character audio** (SCRIPT SFX banks), with subtitles, then hang up.

### Messages
Incoming texts from the browser show as `SMS: ...` and a “1 NEW TEXT” pager.

Enter opens CJ reply presets:

- On my way
- Meet at Grove
- Can't talk busy
- Where you at?

Those replies appear in the browser chat as **CJ**.

### Camera
Enter snaps a photo. Keep the bridge running so the Photos tab gets it.

## Browser

1. Run `bridge/START_GROVELINK.bat`
2. On the real phone or PC open the printed `http://LAN-IP:8088`
3. CHAT tab texts CJ. PHOTOS tab shows snaps.

## Install

1. Compile `GroveLinkPhone.txt` in Sanny Builder → `[GTA SA]\CLEO\GroveLinkPhone.cs`
2. Copy `GroveLink.fxt` → `[GTA SA]\CLEO\GroveLink.fxt`
3. Copy `GroveLink/link.ini` → `[GTA SA]\CLEO\GroveLink\link.ini`
4. Needs CLEO **IniFiles.cleo**
5. Run `START_GROVELINK.bat`, launch GTA, press **K**
