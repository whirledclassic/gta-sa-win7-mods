# GroveLink troubleshooting

## I press K and nothing appears

1. `[GTA]\\CLEO\\GroveLinkPhone.cs` must exist and be larger than a few hundred bytes. Compile `grovelink\\GroveLinkPhone.txt` in Sanny (F7) and copy the `.cs` next to `CLEO.asi`.
2. You need **CLEO 4.3 or 4.4**. `CLEO.asi` sits next to `gta_sa.exe`.
3. Run **CHECK.bat** as admin.

## Phone box is there but the words are blank

`GroveLink.fxt` is not in `[GTA]\\CLEO\\`. Run **PATCH.bat**.

## Browser cannot text CJ

Desktop **START_GROVELINK.bat** stays open. `CLEO\\IniFiles.cleo` present. Firewall TCP 8088. Same LAN.

## Switcher: H does nothing

On foot, within 22 m of a story ped. Cutscenes block the switch. Compile `switcher\\MissionSwitcher.txt` to `CLEO\\MissionSwitcher.cs`.

## Two Sweets on screen

Old `.cs`. v6 hides the original. Run PATCH.bat / CHECK.bat.

## INSTALL cannot find the game

Paste the folder that contains `gta_sa.exe`. It is saved as `GTA_DIR.txt`.
