# Install and patch

Works on **Windows 7** with GTA San Andreas **PC 1.0** + CLEO 4.3/4.4.

## First time

1. Install [CLEO](https://cleo.li) so `CLEO.asi` and `CLEO\IniFiles.cleo` exist.
2. Install [Sanny Builder](https://sannybuilder.com) (3 or 4).
3. Extract this repo (or `git clone`).
4. Right-click **`INSTALL.bat` → Run as administrator**.

The installer:

- Finds `gta_sa.exe` on C/D/E and in the registry
- Copies `GroveLink.fxt` and `link.ini` into `CLEO`
- Compiles the phone and mission switcher when it finds `sanny.exe`
- Writes version `CLEO\GroveLink\installed.txt`
- Allows TCP **8088** in the firewall
- Puts `START_GROVELINK.bat` and `PATCH_GROVELINK.bat` on the Desktop

If Sanny is missing, open `grovelink\GroveLinkPhone.txt` yourself, press **F7**, copy `GroveLinkPhone.cs` into `[GTA]\CLEO\`.

## Every later update

Same folder as the repo:

```
UPDATE.bat
```

That runs `git pull` when Git is installed, then patches.

No Git? Download a new zip, extract over the old folder, run **`PATCH.bat`**.

`PATCH.bat` is safe to run anytime. It overwrites game files from this folder and recompiles.

## After install

1. Double-click Desktop **START_GROVELINK.bat** and leave it open.
2. Start GTA.
3. Press **K**. Green phone on the right.
4. On a phone or PC on the same Wi-Fi, open the URL the bat prints (`http://LAN-IP:8088`).
