# GTA San Andreas — Windows 7 Mods

Single-player CLEO mods for **GTA SA PC 1.0**.

| Mod | What it does |
|-----|----------------|
| [GroveLink Phone](grovelink/) | On-screen cellphone: contacts, **game voice calls**, camera, **two-way browser texts**. |
| [Mission Switcher](switcher/) | Stand next to Sweet/Smoke/Ryder/Cesar, press **H**. **J** back to CJ. |

Not affiliated with Rockstar Games.

## Auto install / auto patch

| Script | Use |
|--------|-----|
| **INSTALL.bat** | First time. Run as admin. |
| **PATCH.bat** | You already installed, this folder is newer. Safe to run again. |
| **UPDATE.bat** | `git pull` then patch. |

Full steps: [docs/INSTALL.md](docs/INSTALL.md)  
Phone keys and screens: [docs/PHONE.md](docs/PHONE.md)  
History: [CHANGELOG.md](CHANGELOG.md)

Current pack version is in `VERSION.txt` (**7**). After a successful install you should see the same number in `[GTA]\CLEO\GroveLink\installed.txt`.

## In game

**K** opens the green GroveLink handset on the right.

Browser chat: start `START_GROVELINK.bat`, open `http://LAN-IP:8088`.

## Requirements

- GTA San Andreas **PC 1.0**
- CLEO **4.3 or 4.4** including `IniFiles.cleo` — https://cleo.li
- Sanny Builder 3 or 4 — https://sannybuilder.com
- Python 2.7.18 or 3.8.10 for the Wi-Fi bridge

## License

MIT. See `LICENSE`.
