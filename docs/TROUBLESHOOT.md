# GroveLink / switcher troubleshooting

## Sanny: Unknown model ID / #FAM1 (error 0083)

CLEO scripts have no SCM header, so names like `#FAM1` will not compile.
`switcher/MissionSwitcher.txt` uses numeric id **105** (FAM1).

Open the updated `MissionSwitcher.txt`, set Sanny edit mode to **GTA San Andreas**, press **F7**, copy `MissionSwitcher.cs` into `[GTA]\CLEO\`.

## Sanny: Incorrect expression 27@ = 22@ (error 0014)

Sanny 3 will not compile a high-level copy between two undeclared locals.
`grovelink/GroveLinkPhone.txt` now declares `22@` / `27@` as Int and uses `0085: 27@ = 22@`.

Pull the latest file, then F7 `grovelink\GroveLinkPhone.txt`. Copy `GroveLinkPhone.cs` into `[GTA]\CLEO\`.

Open Sanny once first: Edit mode = **GTA San Andreas**.

## I press K and nothing appears

1. `[GTA]\CLEO\GroveLinkPhone.cs` must exist and be larger than a few hundred bytes.
2. You need **CLEO 4.3 or 4.4**. `CLEO.asi` sits next to `gta_sa.exe`.
3. Run **CHECK.bat** as admin.
