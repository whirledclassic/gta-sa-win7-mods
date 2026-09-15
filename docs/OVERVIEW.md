# Both mods — what they are and how to run them

Windows 7 / GTA SA PC 1.0 / CLEO 4.3 or 4.4 / Sanny Builder 3 or 4

## 1. GroveLink phone  (`grovelink/GroveLinkPhone.txt`)

In-game Nokia-style phone. **K** opens it.

- Contacts: Sweet, Smoke, Ryder, Cesar, OG Loc, Kendl (scripted lines + WAV ids)
- Messages: two-way SMS through `cleo\\GroveLink\\link.ini` and the Python bridge on port 8088
- Camera: `0A1E` photo
- Compile fixes already in this file: `var` block, opcode `0085` instead of `27@ = 22@`, `:FORCE_CLOSE` label
- Extra fix you want: on close, `03F0: enable_text_draw 0` so the HUD does not stay in text-draw mode

Keys: K open/close, Up/Down, Enter, Backspace.

Desktop: `START_GROVELINK.bat` then open `http://LAN-IP:8088`

## 2. Companion switcher  (`switcher/MissionSwitcher.txt`)

Play as the homie. **CJ stays as a bot** (foot, shotgun, or his own BMX).

**Working complete source** is still commit `ce080795` (v7, ~21 KB).
Current `main` copy is a truncated stub — do not F7 it.

```
git fetch origin
git checkout ce080795 -- switcher/MissionSwitcher.txt
```

Then optional QoL from `switcher/UPGRADE_V82.txt` (P = pull CJ, heal, tighter follow).

Keys (v7 / v8.2):
H / F6 become · G next · J you are CJ · U reset · N bot on/off
B hold · T Sweet · I bike · P pull CJ (v8.2) · L status

Story missions follow YOU. CJ cannot finish a checkpoint alone.

## Compile both

Sanny → mode GTA San Andreas → F7 each `.txt` → copy `.cs` into `[GTA]\\CLEO\\`
