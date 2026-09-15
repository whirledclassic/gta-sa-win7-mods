# Companion switcher v7.0

Play as Sweet, Smoke, Ryder, Cesar, Grove FAM, and the rest. **CJ stays in the world** as a bot: he walks, rides shotgun, or gets his **own BMX** and keeps the first-mission bicycle run going.

## First mission / bicycles

Old v6 dumped CJ off bikes and ignored anyone already riding. That broke *In the Beginning* / *Sweet & Kendl*.

v7:
- **H works while you are on a BMX**
- Homies who are already riding are valid targets
- After you switch, press **I** or just ride — CJ is given BMX **481** and drives after you
- If he falls behind (~28 m) his bike is snapped back onto your line
- Cars still use shotgun. Bikes never try passenger seats.

You are still the player actor. Story triggers follow **you**. The hidden original ped stays alive so mission scripts keep seeing Sweet/Smoke. CJ is the extra body that looks like the homie riding with the pack.

## Play loop

1. Load a save. Toast: `SWITCHER V7`.
2. Stand or **ride next to a homie**. Or press **T**.
3. `SWEET NEAR - PRESS H` → **H** or **F6**.
4. You take their look. CJ is already beside you.
5. Bike? CJ should mount a BMX. If not, tap **I**.
6. **J** to be CJ again.

## Keys

| Key | Action |
|-----|--------|
| **H** or **F6** | Become nearest companion (45 m, including riders) |
| **G** | Next companion |
| **J** | You are CJ again |
| **U** | Hard reset |
| **N** | Send CJ away / call him back |
| **B** | CJ hold here / CJ on me |
| **T** | Call Sweet in |
| **I** | Give CJ a BMX now |
| **L** | Status (foot / shotgun / bike) |

## Notes

- Cutscenes still block the switch.
- Do not hide a rider off their bike — v7 leaves a driving original on the vehicle.
- **B** if he blocks a door, **N** to dismiss, **J** before a heavy cutscene.
- Numeric IDs only (`105` not `#FAM1`, `481` not `#BMX`).
