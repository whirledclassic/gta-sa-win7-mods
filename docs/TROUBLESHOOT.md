# GroveLink / switcher troubleshooting

## Sanny: Unknown model ID / #FAM1 (error 0083)

CLEO scripts have no SCM header, so names like `#FAM1` will not compile.
Pack **main** now uses numeric id **105** (FAM1) in `switcher/MissionSwitcher.txt`.

Open the **updated** `MissionSwitcher.txt`, set Sanny edit mode to **GTA San Andreas**, press **F7**, copy `MissionSwitcher.cs` into `[GTA]\CLEO\`.

## Sanny: Incorrect expression 27@ = 22@

Pack **17** fixes that on the phone script. Do not F7 an old file. Pull / extract the current folder, then compile `grovelink\GroveLinkPhone.txt`.

Open Sanny once first: Edit mode = **GTA San Andreas**.

## I press K and nothing appears

1. `[GTA]\CLEO\GroveLinkPhone.cs` must exist and be larger than a few hundred bytes. If it is missing, F7 `grovelink\GroveLinkPhone.txt` and copy the `.cs` into `CLEO`.
2. You need **CLEO 4.3 or 4.4**. `CLEO.asi` sits next to `gta_sa.exe`.
3. Run **CHECK.bat** as admin.
