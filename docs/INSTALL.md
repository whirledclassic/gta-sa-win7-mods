# Install and patch

Works on **Windows 7** with GTA San Andreas **PC 1.0** + CLEO 4.3/4.4.

## First time (auto)

1. Install [CLEO](https://cleo.li) so `CLEO.asi` and `CLEO\\IniFiles.cleo` sit next to `gta_sa.exe`.
2. Install [Sanny Builder](https://sannybuilder.com) 3 or 4.
3. Right-click **`INSTALL.bat` → Run as administrator**.

If the game is not in a common folder, paste the folder that contains `gta_sa.exe`. That path is saved as `GTA_DIR.txt` in this pack. Next run is silent.

The installer:

- Finds `gta_sa.exe` (Steam, Rockstar, C/D/E Games, registry, then `GTA_DIR.txt`, then a prompt)
- Copies `GroveLink.fxt` into `CLEO`
- Copies sources into `CLEO\\GroveLink\\src`
- Creates `link.ini` only if missing
- Compiles **phone + switcher** when it finds `sanny.exe` (including PATH)
- Writes `CLEO\\GroveLink\\installed.txt`
- Allows TCP **8088**
- Desktop: `START_GROVELINK`, `PATCH_GROVELINK`, `UPDATE_GROVELINK`, `CHECK_GROVELINK`

No Sanny? It writes Desktop `HOW_TO_COMPILE_GROVELINK.txt` with the two F7 steps.

## Later

`CHECK.bat` or Desktop **CHECK_GROVELINK.bat**.  
`UPDATE.bat` if this folder is a git clone.  
`PATCH.bat` anytime. It will not wipe `link.ini`.

## After install

1. Desktop **START_GROVELINK.bat** (phone chat).
2. Start GTA.
3. **K** = phone. **H** next to Sweet = you are Sweet, CJ stays.
