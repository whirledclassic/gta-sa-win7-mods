# GroveLink research → features (v2.2.0)

Short summary of companion-phone / gallery UX we studied and why we shipped these enhancements (not a full taxi/homie phone clone).

## Sources (themes)

| Theme | What we looked at | Takeaway for GroveLink |
|-------|-------------------|------------------------|
| **GTA SA interactive phone mods** | Community CLEO packs with calls, status, camera, maps | Users expect camera + inbox + status on one “phone”; heavy spawn/call systems conflict with other CLEO packs |
| **Companion apps** | RDR2 companion, GTA iFruit, PlayStation App | Live status, gallery, chat, and spectate/second-screen are the sticky features — not full game control |
| **GTA VI phone (public previews)** | Texts, Snapmatic-style gallery, status | Texts + photo gallery + lightweight status remain the core loop |
| **Mobile gallery / PWA UX** | Favorites, Web Share, Add to Home Screen, notifications | Star favorites, share URLs, installable shortcut, optional reply alerts |

## What we implemented

| Research cue | GroveLink 2.x feature |
|--------------|-------------------------|
| Gallery favorites | ★ star + **Favorites** tab; `localStorage` + optional `POST /favorite` → `photos_favorites.json` |
| Share photos / stories | Existing photo **Web Share** / copy; Herald **Share article** on `/news/<id>` |
| Pull / browse | Light **pull-to-refresh** on the phone page |
| Chat as companion thread | **Unread badge** for CJ replies; **Enable CJ alerts** (`Notification`, fail-soft on HTTP LAN); **Mark chat read** |
| Spectate / second screen | Fullscreen, pause/resume, **frame age**, **“snapshot live — not video”** banner; hotter poll when `SPECTATE.on` |
| Herald location | Keep 📍 badge; **Camera ≠ NEWS** unchanged |
| Live status HUD | CLEO writes safe `STATUS.wanted/money/zone/hour/spectate`; bridge `/api` **`hud`**; header strip + optional SA time |
| Installable phone page | **`/manifest.webmanifest`** + apple meta (Add to Home Screen) |
| Companion quick access | **Quick Actions**: Camera tip, Spectate, Herald, Text CJ |
| Social nick / live crowd / stories | **Chat nicknames**, spectate **N watching**, **Moments** Today reel, wanted toasts, **By place** gallery |
| Reactions / pin / recap / cinema | **Chat reactions** + **pin**, `/recap`, spectate **cinema** (H), bridge **uptime** (2.2.0) |

## Out of scope (vs Ultimate Interactive Phone)

**Not implemented:** full taxi / homie spawn / call ped systems, map blips as a second GPS, or any opcode-heavy “real cellphone” that fights other CLEO packs.

Reasons: crash-safer surface only (no `hold_cellphone`, no `033E`); Win7 stdlib bridge; Camera stays photo-only; NEWS stays separate; spectate is snapshots not video.

See [FEATURES.md](FEATURES.md) and root [CHANGELOG.md](../CHANGELOG.md).
