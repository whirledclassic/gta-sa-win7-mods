# GTA San Andreas — Windows 7 Mods

Two single-player CLEO mods for **GTA SA PC 1.0** on **Windows 7**.

| Mod | What it does |
|-----|----------------|
| [GroveLink Phone](grovelink/) | In-game phone takes a photo and pushes it to your **real phone** on the same Wi-Fi. The real phone can send a text that appears in GTA as an SMS. |
| [Mission Switcher](switcher/) | Stand next to Smoke, Sweet, Ryder, Cesar… press **H** to play as them. Press **J** to return to CJ. |

Not affiliated with Rockstar Games. Single-player only.

## Requirements (both mods)

- GTA San Andreas **PC 1.0** (DVD / downgraded). Steam “latest” often breaks CLEO on Win7.
- **CLEO 4.3 or 4.4** from [cleo.li](https://cleo.li) — include `IniFiles.cleo`
- **Sanny Builder 3** from [sannybuilder.com](https://sannybuilder.com)
- GroveLink also needs **Python 2.7.18 or 3.8.10** (3.9+ will not run on Windows 7)

## Quick start — GroveLink

1. Compile `grovelink/GroveLinkPhone.txt` → copy `GroveLinkPhone.cs` into `[GTA SA]\CLEO\`
2. Copy `grovelink/GroveLink/link.ini` to `[GTA SA]\CLEO\GroveLink\link.ini`
3. Edit `grovelink/bridge/config.ini` if your game path is not the default
4. Run `grovelink/bridge/START_GROVELINK.bat` and allow port **8088**
5. On your phone, open the printed URL, e.g. `http://192.168.1.42:8088`
6. In game press **K**, open **CAMERA**, press **Enter**

## Quick start — Switcher

1. Compile **one** of:
   - `switcher/MissionSwitcher.txt` (skin + Grove “CJ-bot”)
   - `switcher/MissionSwitcher_SkinOnly.txt` (safer, skin only)
2. Copy the `.cs` into `[GTA SA]\CLEO\`
3. Stand next to a story companion, press **H**. **J** restores CJ.

Do not install both switcher scripts at once.

## Honest limits

- GroveLink is a **same-Wi-Fi browser link**. It is not iMessage, WhatsApp, or carrier SMS.
- The switcher changes **your** model. Mission scripts still treat you as the player. That is why most missions do not instantly fail — and also why this is not a GTA V protagonist system.
- Cutscenes snap back to the original models.

## Layout

```
grovelink/
  GroveLinkPhone.txt      CLEO source
  GroveLink/link.ini      shared state with the PC bridge
  bridge/                 Python 2/3 server + Start bat
switcher/
  MissionSwitcher.txt
  MissionSwitcher_SkinOnly.txt
```

## License

MIT. See `LICENSE`.
