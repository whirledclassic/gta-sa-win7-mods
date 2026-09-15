# Companion switcher v6.1

Play as Sweet, Smoke, Ryder, Cesar and the rest. **CJ stays in the world** and rides with you.

## Play loop

1. Stand next to them on foot.
2. Press **H**. You take their place and heading.
3. CJ is already beside you. Drive — he takes shotgun. Get out — he hops out.
4. Press **J** when you want to be CJ again.

The original ped is hidden, locked, and kept a couple of metres off you so mission scripts still see him.

## Keys

| Key | Action |
|-----|--------|
| **H** | Become the nearest story companion (22 m) |
| **G** | Next companion in range |
| **J** | You are CJ again |
| **R** | Hard reset |
| **N** | Send CJ away / call him back |
| **B** | CJ hold here / CJ on me |

## v6.1 quality / efficiency

- Same CJ body is reused if you switch again
- Same ped + **H** = `ALREADY THEM` (no reload)
- Follow task only when he is actually behind
- Weapon copy only on weapon change
- Hidden ped offset so he does not bump you
- Faster key repeat and faster FAM1 fallback
- Scan skips the hidden original and the CJ body

## Files

`MissionSwitcher.txt` — this v6.1 (INSTALL compiles it).  
`MissionSwitcher_SkinOnly.txt` — look like them, no extra CJ body.

## If it feels off

- Grove FAM1 face = player model 0 did not stream.
- No bikes.
- **B** if he blocks a door, **N** to dismiss, **J** before a heavy cutscene.
- Get out of the car before **H**.
