# Install and patch

Works on **Windows 7** with GTA San Andreas **PC 1.0** + CLEO 4.3/4.4.

## First time

1. Install [CLEO](https://cleo.li) so `CLEO.asi` and `CLEO\\IniFiles.cleo` exist.
2. Install [Sanny Builder](https://sannybuilder.com) (3 or 4).
3. Extract this repo (or `git clone`).
4. Right-click **`INSTALL.bat` → Run as administrator**.

The installer:

- Finds `gta_sa.exe` on C/D/E, Steam common folders, Rockstar folders, and the registry
- Copies `GroveLink.fxt` into `CLEO` (labels for the phone screen)
- Creates `CLEO\\GroveLink\\link.ini` only if it is missing (later patches keep your texts)
- Compiles the phone and mission switcher when it finds `sanny.exe`
- Writes version `CLEO\\GroveLink\\installed.txt`
- Allows TCP **8088** in the firewall
- Puts four Desktop launchers that still point at **this repo folder**:
  - `START_GROVELINK.bat`
  - `PATCH_GROVELINK.bat`
  - `UPDATE_GROVELINK.bat`
  - `CHECK_GROVELINK.bat`

If Sanny is missing, open `grovelink\\GroveLinkPhone.txt` yourself, press **F7**, copy `GroveLinkPhone.cs` into `[GTA]\\CLEO\\`.

## Every later update

Same folder as the repo:

```
UPDATE.bat
```

That runs `git pull` when Git is installed, then patches.

No Git? Download a new zip, extract over the old folder, run **`PATCH.bat`** or **`CHECK.bat`**.

`PATCH.bat` is safe to run anytime. It overwrites game files from this folder and recompiles. It does **not** wipe `link.ini`.

## Missed an update

`CHECK.bat` reads `[GTA]\\CLEO\\GroveLink\\installed.txt`, compares it to `VERSION.txt` in this folder, and patches if you are behind. Run it whenever the phone looks old or blank.

## After install

1. Double-click Desktop **START_GROVELINK.bat** and leave it open.
2. Start GTA.
3. Press **K**. Green phone on the right: signal bars, GROVELINK title, Contacts / Messages / Camera / Close.
4. On a phone or PC on the same Wi-Fi, open the URL the bat prints (`http://LAN-IP:8088`).
