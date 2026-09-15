# GTA San Andreas — Windows 7 Mods

Two single-player CLEO mods for **GTA SA PC 1.0** on **Windows 7**.

| Mod | What it does |
|-----|----------------|
| [GroveLink Phone](grovelink/) | Real in-game cellphone with **on-screen contacts**. Photos go to your **real phone** on the same Wi-Fi. |
| [Mission Switcher](switcher/) | Stand next to Smoke, Sweet, Ryder, Cesar… press **H**. **J** returns to CJ. |

Not affiliated with Rockstar Games. Single-player only.

## Install

1. Extract the zip to Desktop or Downloads.
2. Right-click **`INSTALL.bat`** → **Run as administrator**.
3. Accept UAC. It finds GTA, copies `.fxt` + `link.ini`, and puts **START_GROVELINK.bat** on the Desktop.
4. Open `grovelink\GroveLinkPhone.txt` in **Sanny Builder** and press **F7**. Copy the new `GroveLinkPhone.cs` into `[GTA SA]\CLEO\`.
5. Double-click **START_GROVELINK.bat**, launch GTA, press **K**.

You should see **GROVELINK** and a contacts menu on the right. Up/Down, Enter, Backspace.

## Requirements

- GTA San Andreas **PC 1.0**
- **CLEO 4.3 or 4.4** from https://cleo.li including `IniFiles.cleo`
- **Sanny Builder 3 or 4** from https://sannybuilder.com
- GroveLink: **Python 2.7.18 or 3.8.10** on Windows 7

## License

MIT. See `LICENSE`.
