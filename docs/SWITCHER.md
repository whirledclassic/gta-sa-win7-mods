# Companion switcher v6.2

Play as Sweet, Smoke, Ryder, Cesar, Grove FAM, and the rest. **CJ stays in the world** and rides with you.

If Grove Street is empty, **T** calls Sweet in. Then **H**.

## Play loop

1. Load a save. You should see `SWITCHER ON` at the top.
2. Stand next to a homie **or press T**.
3. When the hint says `SWEET NEAR - PRESS H`, press **H** (or **F6**).
4. You take their place. CJ is already beside you.
5. Drive a car (not a bike) — CJ takes shotgun.
6. **J** when you want to be CJ again.

The original ped is hidden, locked, and kept a few metres off you so mission scripts still see him.

## Keys

| Key | Action |
|-----|--------|
| **H** or **F6** | Become the nearest companion (40 m) |
| **G** | Next companion in range |
| **J** | You are CJ again |
| **U** | Hard reset (was **R** — **R is reload**, that was breaking it) |
| **N** | Send CJ away / call him back |
| **B** | CJ hold here / CJ on me |
| **T** | Call Sweet in if nobody is around |
| **L** | Status line — tells you if the script is live |

## Why H used to look dead

- Story peds are not standing on Grove 24/7. H only finds *them* (plus Grove FAM 105/106/107). Empty street = `NOBODY NEAR`.
- **R** was hard reset. Reloading a gun dumped you back to CJ.
- Radius was 22 m. It is 40 m now.
- Cutscene / in-car blocks the switch and says so.

## v6.2

- Boot toast so you know `MissionSwitcher.cs` loaded
- Live `SWEET NEAR - PRESS H` ping
- **T** summons Sweet
- Grove FAM on Grove Street are valid targets
- Clear fail text: car / cutscene / nobody / press T
- Hidden original offset 3.4 m + re-lock every watchdog tick
- Reset moved to **U**
- **F6** is an extra Become key
- **L** status

## Files

`MissionSwitcher.txt` — this v6.2 (INSTALL compiles it).  
`MissionSwitcher_SkinOnly.txt` — look like them, no extra CJ body.

## If it feels off

- No `SWITCHER ON` toast = `.cs` is not in `CLEO\`. Run INSTALL/CHECK, or Sanny F7 the txt.
- Grove FAM1 face on the CJ body = player model 0 did not stream. Fine, he still follows.
- No bikes.
- **B** if he blocks a door, **N** to dismiss, **J** before a heavy cutscene.
- Get out of the car before **H** or **T**.
