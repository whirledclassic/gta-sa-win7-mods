# GroveLink troubleshooting

## I press K and nothing appears

1. `[GTA]\\CLEO\\GroveLinkPhone.cs` must exist and be larger than a few hundred bytes. If it is missing, compile `grovelink\\GroveLinkPhone.txt` in Sanny (F7) and copy the `.cs` next to `CLEO.asi`.
2. You need **CLEO 4.3 or 4.4**. `CLEO.asi` sits next to `gta_sa.exe`.
3. Run **CHECK.bat** as admin.

## Phone box is there but the words are blank

`GroveLink.fxt` is not in `[GTA]\\CLEO\\`. Run **PATCH.bat**. Do not put the FXT inside `CLEO\\GroveLink\\` — it has to sit in `CLEO\\` itself.

## Contacts do not highlight / I cannot move

Use the arrow keys, not W/S. Enter selects. Backspace goes back. If the game remapped those keys, temporarily use the defaults.

## Call audio is silent

Those IDs are stock SCRIPT SFX banks (Sweet 29000, Smoke 28800, Ryder 20200, Cesar 25200, OG Loc 27400, Kendl 27000, ring 23000). They only exist on **PC 1.0** audio. SilentPatch is fine. A replaced `audio\\SFX` folder can drop the banks.

Backspace hangs up. The ON CALL screen must stay visible during the lines — if it never appears you are still on an old `.cs`. Run **PATCH.bat**.

## Browser cannot text CJ

1. Desktop **START_GROVELINK.bat** stays open.
2. `CLEO\\IniFiles.cleo` is present.
3. Windows firewall allows TCP **8088** (the installer adds the rule).
4. Phone and PC are on the same LAN. Use the IPv4 the bat prints, not 127.0.0.1, from the other device.
5. `CLEO\\GroveLink\\link.ini` exists. The installer will not overwrite a live inbox.

## Desktop START_GROVELINK does nothing

v7 copied the bridge bat onto the Desktop, so it looked for `grovelink_server.py` on the Desktop and failed. v8 writes a launcher that `cd`s into this repo's `grovelink\\bridge` folder. Run **PATCH.bat** once to refresh the Desktop shortcuts.

## I missed several updates

Run **UPDATE.bat** (Git) or download a new zip, extract over the repo folder, then **CHECK.bat**.
