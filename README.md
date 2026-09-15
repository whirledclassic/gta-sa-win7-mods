# GTA San Andreas — Windows 7 Mods

Two single-player CLEO mods for **GTA SA PC 1.0** on **Windows 7**.

| Mod | What it does |
|-----|----------------|
| [GroveLink Phone](grovelink/) | Real in-game cellphone. Photos go to your **real phone** on the same Wi-Fi. |
| [Mission Switcher](switcher/) | Stand next to Smoke, Sweet, Ryder, Cesar… press **H**. **J** returns to CJ. |

Not affiliated with Rockstar Games. Single-player only.

## One-click install (beginners start here)

1. Extract the zip to Desktop or Downloads.
2. Right-click **`INSTALL.bat`** → **Run as administrator**.
3. Accept UAC and wait. It will:
   - Find GTA SA (common folders + registry)
   - Copy GroveLink `fxt` + `link.ini`
   - Compile **GroveLinkPhone** with Sanny Builder if `sanny.exe` is found
   - Optionally compile **MissionSwitcher_SkinOnly** (safer switcher)
   - Create Gallery folders, write bridge `config.ini`, open firewall TCP **8088**
   - Put **GroveLink Phone** shortcut, `START_GROVELINK`, **`VERIFY_GROVELINK.bat`**, **`GroveLink_README.txt`**, and `GroveLink_PHONE_URL.txt` on the Desktop
4. Follow the green **SUCCESS** screen — only **3 steps**:

   1. Double-click Desktop **GroveLink Phone** (keep the bridge window open)  
   2. Launch GTA San Andreas  
   3. Press **K** → **Camera** → **Enter** (or **Space**)

Optional: double-click Desktop **`VERIFY_GROVELINK.bat`** anytime for a plain-English OK/MISSING health check (game, CLEO, phone script, `link.ini`, Python, `config.ini`, `GroveLinkPhone.txt`, writable `bridge/photos`, firewall note, URLs). Desktop **`GroveLink_README.txt`** repeats the 3 steps and points at `grovelink/TROUBLESHOOTING.md`.

If Sanny was not found, INSTALL prints exact download + F7 steps. It **never deletes** a working `GroveLinkPhone.cs` without a newly compiled replacement. Do **not** use the tiny old stub in `grovelink/prebuilt/`.

### Requirements

- GTA San Andreas **PC 1.0**
- **CLEO 4.3 or 4.4** from https://cleo.li including `IniFiles.cleo`
- **Sanny Builder 3 or 4** from https://sannybuilder.com (once, unless INSTALL finds and compiles with it)
- GroveLink bridge: **Python 2.7.18 or 3.8.10** on Windows 7 (stdlib only)

### Verify GroveLink camera → phone page

1. Keep the bridge window open (**GroveLink Phone** / START_GROVELINK).
2. On the PC: **http://127.0.0.1:8088** (often opens automatically).
3. On your phone (same Wi-Fi): **http://LAN-IP:8088** (printed by the bridge / `OPEN_ON_PHONE.txt`).
4. Health check: **http://127.0.0.1:8088/health** or Desktop **VERIFY_GROVELINK.bat**.
5. In GTA: **K** → Camera → **Enter** or **Space** — shot appears within a couple of seconds. Menu includes **HELP** (reminds you to open START GROVELINK on the PC).

Phone page extras: **All / Today** album tabs, quick-reply chips, file size in the meta line, large tap-to-copy **IP:port** (and `/qr` share page — no QR library), Delete (bridge cache only), auto-prune when `server.max_photos` (default **40**) is exceeded.

Stuck? See [grovelink/TROUBLESHOOTING.md](grovelink/TROUBLESHOOTING.md).

## Advanced / manual

- GroveLink details: [grovelink/README.md](grovelink/README.md)
- Mission Switcher: [switcher/README.md](switcher/README.md)

## License

MIT. See `LICENSE`.
