# GroveLink changelog

Human-readable highlights from pack **1.0 → 2.1.0**. Full detail also lives in root `README.md` round notes and [grovelink/FEATURES.md](grovelink/FEATURES.md).

## 2.1.0 — Nicknames, watching, Moments, wanted toasts, By place

- **Chat nicknames:** web visitors set a display name (localStorage); sent with `/send` as `from=` / `name=`; shown in thread; default **REAL PHONE** if empty.
- **Spectate viewer count:** track recent `/spectate` + `/api/spectate` polls (IP + ~30s) in STATE; show **N watching** on spectate page + Quick Actions.
- **Moments reel:** story-style **Today** strip at top of gallery (today's photos by mtime); tap opens lightbox.
- **Wanted toasts:** when `/api` `hud.wanted` increases → flash **WANTED ★ increased** (fail-soft).
- **By place:** gallery tab listing zones (Herald `location` + caption tags) with counts; filter shots by place.
- Docs: FEATURES / CHANGELOG / RESEARCH; smoke covers nicknames, watching, places, Moments, toast hooks; VERSION **2.1.0**.

## 2.0.0 — Research-backed phone companion pass

- **Gallery favorites:** ★ star + Favorites filter; persist `localStorage` + optional bridge `photos_favorites.json` (`GET/POST /favorite`).
- **Share:** Web Share / copy for photos (kept); Herald article **Share** button; light pull-to-refresh.
- **Chat:** unread badge for CJ replies; optional browser **Notification** (request on button, fail-soft on HTTP LAN); mark chat read.
- **Spectate:** fullscreen, pause/resume, last-frame age, **snapshot live — not video** banner; hotter refresh when `SPECTATE.on`.
- **Herald:** Web Share on article; location badge kept; Camera ≠ NEWS unchanged.
- **STATUS / HUD:** CLEO periodically writes safe `STATUS.wanted/money/zone/hour/spectate` when `bridge=1`; phone header second-screen HUD + `/api` `hud`; optional SA time strip.
- **PWA-lite:** `/manifest.webmanifest` + better Add to Home Screen meta.
- **Quick Actions** bar: Camera tip, Spectate, Herald, Text CJ.
- **Out of scope:** full taxi/homie spawn/call (documented in `grovelink/RESEARCH.md` vs Ultimate Interactive Phone).
- Docs: RESEARCH / FEATURES / README / CHANGELOG; smoke covers favorites, manifest, hud, VERSION **2.0.0**.

## 1.9.0 — CJ replies + LIVE SPECTATE

- **CJ replies to web chats:** CLEO **REPLY** menu — Up/Down pick canned line ("On my way", "Who is this?", "Grove forever", "Busy rn", "Where you at?") → Enter writes `[OUTBOX] new=1` `msg=` `from=CJ`. Bridge clears flag, appends chat log as CJ; `/api` + `/api/chat` expose thread; web styles **CJ vs visitor** bubbles ("Delivered to CJ" / "CJ replied").
- **LIVE SPECTATE (snapshots):** `GET /spectate` full-viewport latest frame, auto-refresh ~750ms, **LIVE SPECTATE** badge, link back to phone page. CLEO **SPECTATE** toggle → `SPECTATE.on`; while on (phone open or closed) every ~2.5s `take_photo` + `SPECTATE.frame=1` (not `PHOTO.take`). Bridge copies on `SPECTATE.frame` or `PHOTO.take`; **never** files Breaking News from spectate. `/api` + `/api/spectate`: `latest_url`, `spectate_on`.
- **Camera stays gallery-only; NEWS stays separate** with location tags.
- Docs: how to reply in-game; spectate limitation (slideshow, low FPS, same Wi-Fi, bridge must run).
- Smoke: OUTBOX→chat; `/spectate` HTML; SPECTATE.frame copy no NEWS; VERSION **1.9.0**.

## 1.8.2 — Breaking News location tags

- **Location tags:** Herald articles store optional `location` (San Andreas place/zone).
- **CLEO NEWS only:** after snap + `NEWS.make=1`, writes `NEWS.zone` (0843 info-zone key + coarse if-ladder: Grove Street / Idlewood / LS Airport / …). **CAMERA never writes NEWS keys.**
- **Bridge:** on `NEWS.make`, reads `NEWS.zone`/`loc` → `create_news_from_photo(..., location=)`; web `POST /news` accepts `location`; headlines use location when present; `/news` + `/news/<id>` show a 📍 location badge.
- **Phone page:** Breaking News confirm dialog — SA place dropdown or typed location before filing.
- Smoke: article with location in HTML; NEWS.make flow with zone in ini; VERSION **1.8.2**.

## 1.8.1 — Camera ≠ Breaking News

- **Camera stays gallery-only:** CLEO CAMERA writes `PHOTO.take` + count only — never news. Shutter burst copies to phone/PC page; **never** creates Herald articles (removed `news.auto` entirely from watcher / config / STATE / prints / docs).
- **NEWS menu (separate):** CLEO slot **NEWS** (order CAMERA / INBOX / NEWS / CONTACTS / STATUS / HELP / CLOSE) snaps + sets `NEWS.make=1`; bridge burst-copies then `create_news_from_photo` on newest bridge shot; `NEWS.new=1` → **NEWS FILED** toast. Web **Breaking News** button / `POST /news` unchanged (no retake).
- HELP text: Camera = pics to phone; NEWS = snap + Grove Street Herald.
- Smoke: PHOTO.take alone must not create news; `NEWS.make=1` creates article; POST /news still PASS; no `news_auto` tests.

## 1.8.0 — Gallery + Breaking News + SMS→CJ

- **Phone gallery:** hero/latest shot, grid feed, optional per-photo **caption** (JSON index + sidecar `.txt`), sticky composer, Share (Web Share / copy), search/sort/tabs/delete/clear/export kept
- **Breaking News:** per-photo button → offline satirical **Grove Street Herald** article (templates + filename/time keywords; no AI APIs); `GET /news`, `GET /news/<id>`, `POST /news`; articles under `bridge/news/*.json`; CLEO **NEWS FILED** via `NEWS.new=1` (1.8.1: NEWS menu / web only — no auto-on-shutter)
- **Text CJ:** `POST /send` writes INBOX (`new=1`, `from=`, `msg=`); optional **From:** field; chat thread shows **Delivered to CJ**; CLEO notifies **SMS FROM REAL PHONE** even when phone closed (once per new)
- **Docs / smoke:** FEATURES, README, TROUBLESHOOTING, CHANGELOG; smoke covers `/news`, create article, `/send` ini, `/api/chat`

## 1.7.1 — Polish / release-ready

- **Stability:** if bridge TCP port is already in use, print plain English **port N busy** (close the other GroveLink window / free the port)
- **Docs:** root README leads with noob path (INSTALL → UPDATE → VERIFY → play); `update.ini` comments + after-merge `branch=main` note
- **Smoke:** harden server ready-wait; VERSION/CHANGELOG checks for **1.7.1**; must PASS 100%
- Bug review of INSTALL / UPDATE / VERIFY / START / bridge / CLEO — real bugs only (no new chrome)
- Keep `update.ini` `branch=fix/grovelink-camera-snapshots` until PR #1 merges

## 1.7.0 — Round 7

- **Phone page help footer** — keyboard shortcut hints (`?` toggles detail, `Esc` closes lightbox/confirm, `/` focuses search)
- **Empty-album UX** — **Clear all** and **Export zip** (and Download latest) stay **disabled** when photo count is 0
- **VERIFY_GROVELINK.bat** — checks root **`VERSION`** file is present and **prints** the pack version
- **CHANGELOG.md** — this file (1.0→1.7 highlights)
- **Smoke tests** — extended for help footer, disabled empty actions, VERIFY VERSION
- CLEO STATUS still flashes photo count (`LIVE N  PHONE PAGE ON PC`); Camera already shows **PHOTO TAKEN #N**

## 1.6.0 — Round 6

- Newest/Oldest **client-side** sort toggle; **Hidden from phone** skip-list note (`skipped_deleted`)
- Favicon-free + Add to Home Screen tip; CLEO **Catalina** contact
- `POST /clear` requires `confirm=1`; `/photo/…` path hardened; START strips VERSION CR
- INSTALL big red **CLEO.asi missing** warning + https://cleo.li

## 1.5.0 — Round 5

- Empty-state large LAN IP; pinch **Delete this shot?**; filename search; **Clear all** (`/clear`)
- `/api` **last_error**; START prints VERSION + Python 3.8.10 help
- CLEO **NO NEW TEXTS**; STATUS **PHONE PAGE ON PC**; UPDATE prints exact zip URL on fail
- Bugfixes: VERIFY `gta_dir` spaces + REPO CR; shutter `take=1` drain
- **`tests/smoke_bridge.py`** + `TEST_BRIDGE.bat`

## 1.4.0 — Round 4

- LIVE pulse + offline reconnect banner; **Export zip**; `server.poll_ms`
- Version + photo stats on page; docs / FEATURES; Win7 mkdir harden

## 1.3.0 — Round 3+update

- Album All/Today tabs; quick-reply chips; tap-to-copy IP + `/qr` (no QR lib)
- `max_photos` prune; CLEO HELP menu; INSTALL Desktop README
- One-click **UPDATE_GROVELINK.bat** (GitHub zip, no Git) + root `VERSION` / `update.ini`

## 1.2.x — Round 2

- **VERIFY_GROVELINK.bat**; phone delete (bridge cache only) + NEW unread badges
- CLEO menu CAMERA / INBOX / CONTACTS / STATUS / CLOSE

## 1.1.x — Round 1 enhance

- One-click **INSTALL.bat**; bridge LAN/localhost, `/health`, lightbox, shutter burst
- CLEO inbox from ini, bridge-down remind, **PHOTO TAKEN #count**
- Docs + TROUBLESHOOTING

## 1.0.x — Foundation / safety

- Crash-safer CLEO: **no** `hold_cellphone`, **no** custom GXT `033E`
- Bridge gallery watch; INSTALL never deletes working `.cs` without replacement
- Stdlib-only Python bridge for **Windows 7** (2.7.18 / 3.8.10)
- No fake full prebuilt `.cs` stub for daily use
