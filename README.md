# GTA San Andreas — Windows 7 Mods

Single-player CLEO mods for **GTA SA PC 1.0**.

| Mod | What it does |
|-----|----------------|
| [GroveLink Phone](grovelink/) | On-screen cellphone: contacts, **game voice calls**, camera, **two-way browser texts**. |
| [Mission Switcher](switcher/) | Stand next to Sweet/Smoke/Ryder/Cesar, press **H**. **J** back to CJ. |

Not affiliated with Rockstar Games.

## Auto install / auto patch / missed update

| Script | Use |
|--------|-----|
| **INSTALL.bat** | First time. Right-click → Run as administrator. |
| **PATCH.bat** | Already installed, this folder is newer. Safe to run again. |
| **UPDATE.bat** | `git pull` then patch. Use this if you missed a release. |
| **CHECK.bat** | Compares pack version vs `[GTA]\CLEO\GroveLink\installed.txt`. Patches if you are behind. |

Full steps: [docs/INSTALL.md](docs/INSTALL.md)  
Phone keys and screens: [docs/PHONE.md](docs/PHONE.md)  
If the screen is blank: [docs/TROUBLESHOOT.md](docs/TROUBLESHOOT.md)  
History: [CHANGELOG.md](CHANGELOG.md)

Current pack version is in `VERSION.txt` (**9**). After a successful install the same number is in `[GTA]\CLEO\GroveLink\installed.txt`.

Missed a week of updates? Run **UPDATE.bat**. No Git? Download a fresh zip, extract over this folder, run **PATCH.bat** or **CHECK.bat**.

## In game

**K** opens the green GroveLink handset on the right.

Home: Contacts, Messages, Camera, **Tools**, Close.
Tools: Grove GPS marker, next radio station.
Browser **RING** makes the in-game phone ring.

Browser chat: start Desktop **START_GROVELINK.bat**, open `http://LAN-IP:8088`.

## Requirements

- GTA San Andreas **PC 1.0**
- CLEO **4.3 or 4.4** including `IniFiles.cleo` — https://cleo.li
- Sanny Builder 3 or 4 — https://sannybuilder.com
- Python 2.7.18 or 3.8.10 for the Wi-Fi bridge

## License

MIT. See `LICENSE`.
