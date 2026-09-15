# Companion switcher v3

Stand next to a story ped and wear their skin. The original ped is hidden (not deleted) so mission scripts keep the handle. **J** puts CJ back and unhides them.

## Keys

| Key | Action |
|-----|--------|
| **H** | Become the nearest story companion (22 m, on foot) |
| **G** | Next companion in range |
| **J** | Restore CJ, unhide original, remove CJ-bot |
| **R** | Hard reset |
| **N** | Toggle the Grove Families CJ-bot that follows you |

First load prints the help line. Get out of a car first. Cutscenes block the switch.

## What it does

1. Finds the closest matching story model (Sweet, Smoke, Ryder, Cesar, OG Loc, Kendl, Truth, Catalina, Woozie, Toreno, and a few other story IDs).
2. Skips peds who are in a vehicle.
3. Changes *your* model and walkstyle. Copies their current weapon (50 rounds).
4. Hides the original ped and puts a radar marker on them.
5. Optionally spawns a FAM1 “CJ” follower. **N** turns that off if it gets in the way.
6. A watchdog re-issues follow and drops the handle if the original ped was removed by a mission.

If you die while switched, CJ is restored automatically.

## Which file to compile

| File | Use |
|------|-----|
| `MissionSwitcher.txt` | Full v3. `INSTALL.bat` compiles this. |
| `MissionSwitcher_SkinOnly.txt` | Skin + walkstyle only. Use this if a mission fights the hidden ped / bot. |

Only one of those `.cs` files should sit in `[GTA]\CLEO\`.

## Troubleshooting

- **NO COMPANION IN 22M** — walk closer. They must be on foot.
- **MODEL DID NOT LOAD** — that DFF is not streamed; try again a second later.
- **WAIT FOR THE CUTSCENE** — the player is locked. Wait until you can move.
- Two bodies after an old v1 install — press **R**, then recompile v3 so the original is hidden instead of cloned.
- Story mission breaks — switch to SkinOnly and press **J** before the next cutscene.
