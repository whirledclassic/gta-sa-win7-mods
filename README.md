# GTA San Andreas — Windows 7 Mods

Two single-player CLEO mods for **GTA SA PC 1.0** on **Windows 7**.

| Mod | What it does |
|-----|----------------|
| [GroveLink Phone](grovelink/) | Real in-game cellphone. Photos go to your **real phone** on the same Wi-Fi. |
| [Mission Switcher](switcher/) | Stand next to Smoke, Sweet, Ryder, Cesar… press **H**. **J** returns to CJ. |

Not affiliated with Rockstar Games. Single-player only.

## Install in one click

1. Extract the zip to Desktop or Downloads.
2. Right-click **`INSTALL.bat`** → **Run as administrator**.
3. Accept UAC. It finds GTA, copies `GroveLink.fxt` + `link.ini`, tries to compile the phone script with Sanny Builder if `sanny.exe` is found, creates the Gallery folder, writes bridge `config.ini`, opens firewall TCP **8088**, and puts **START_GROVELINK** on the Desktop.
4. Double-click **START_GROVELINK**, launch GTA, press **K**.

If Sanny was not found, open `grovelink\GroveLinkPhone.txt` in Sanny Builder, press **F7**, and copy `GroveLinkPhone.cs` into `[GTA]\CLEO\`. INSTALL no longer deletes a working phone script when compile is skipped.

## Verify GroveLink camera → phone page

1. Keep the bridge window open (START_GROVELINK).
2. On the PC open **http://127.0.0.1:8088**
3. On your phone (same Wi-Fi) open **http://LAN-IP:8088** (IP is printed by the bridge).
4. In GTA: **K** → Camera → **Enter** or **Space**.
5. Within a couple of seconds the shot should appear on `/` and `/api`.

## Requirements

- GTA San Andreas **PC 1.0**
- **CLEO 4.3 or 4.4** from https://cleo.li including `IniFiles.cleo`
- **Sanny Builder 3 or 4** from https://sannybuilder.com (once, unless INSTALL finds and compiles with it)
- GroveLink: **Python 2.7.18 or 3.8.10** on Windows 7

## License

MIT. See `LICENSE`.
