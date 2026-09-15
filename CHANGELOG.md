# GroveLink changelog

Human-readable highlights from pack **1.0 → 1.8.1**. Full detail also lives in root `README.md` round notes and [grovelink/FEATURES.md](grovelink/FEATURES.md).

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
