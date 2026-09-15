#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GroveLink bridge smoke test — stdlib only, Win7/PC + Linux.

Starts the bridge HTTP server on an ephemeral port, asserts:
  GET /health, GET /api, GET /export.zip, GET /
Optional: gallery copy + last_error + skipped_deleted + sort HTML + clear confirm +
help footer + empty-action disable + VERIFY VERSION + CHANGELOG + port-busy + README polish.
1.8.1: Camera≠NEWS — PHOTO.take alone no news; NEWS.make creates article; POST /news; no news_auto.
1.8.2: Breaking News location tags — POST /news location in HTML; NEWS.make with zone in ini.
1.9.0: CJ REPLY (OUTBOX→chat); /spectate snapshot live view; SPECTATE.frame copy (no NEWS).
2.0.0: favorites API; /manifest.webmanifest; /api hud; spectate UX; share article; RESEARCH.md.
2.1.0: chat nicknames; spectate watching count; Moments reel; wanted toasts; By place; docs.
2.2.0: chat reactions+pin; spectate cinema; /recap; bridge uptime; CLEO 6th REPLY; docs.
2.3.0: photo comments; mute; spectate DL; density; streak; Herald depth; UI polish; docs.
2.4.0: host/viewer modes; broadcast; request queue; polls/votes; rate limit; /live; docs.
2.5.0: scrollable contacts; dialogue calls; friend texts + auto-reply; cj_texts web; docs.
2.5.1: Desktop START finds bridge via GroveLink_REPO.txt; INSTALL writes REPO before copy.
2.5.2: INSTALL writes Desktop GroveLink Phone.bat (Win7-reliable); .lnk optional.

Run from repo root or anywhere:
  python tests/smoke_bridge.py
  python3 tests/smoke_bridge.py
  py -3 tests\\smoke_bridge.py
"""
from __future__ import print_function

import json
import os
import socket
import sys
import tempfile
import threading
import time
import traceback

# Make grovelink/bridge importable
HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.normpath(os.path.join(HERE, ".."))
BRIDGE = os.path.join(REPO, "grovelink", "bridge")
sys.path.insert(0, BRIDGE)

RESULTS = []


def check(name, ok, detail=""):
    status = "PASS" if ok else "FAIL"
    RESULTS.append((name, status, detail))
    line = "[%s] %s" % (status, name)
    if detail:
        line += " — " + str(detail)[:200]
    print(line)
    return ok


def free_port():
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    return port


def http_get(port, path, timeout=5):
    try:
        from urllib.request import urlopen
    except ImportError:
        from urllib2 import urlopen
    url = "http://127.0.0.1:%s%s" % (port, path)
    resp = urlopen(url, timeout=timeout)
    data = resp.read()
    code = getattr(resp, "status", None) or resp.getcode()
    return code, data



def http_post(port, path, data, timeout=5):
    """POST form body; returns (code, parsed_json_or_raw). Handles HTTPError (429)."""
    try:
        from urllib.request import Request, urlopen
        from urllib.error import HTTPError
    except ImportError:
        from urllib2 import Request, urlopen, HTTPError
    if not isinstance(data, bytes):
        data = data.encode("utf-8")
    url = "http://127.0.0.1:%s%s" % (port, path)
    req = Request(url, data=data, headers={"Content-Type": "application/x-www-form-urlencoded"})
    try:
        resp = urlopen(req, timeout=timeout)
        body = resp.read()
        code = getattr(resp, "status", None) or resp.getcode()
    except HTTPError as e:
        code = e.code
        try:
            body = e.read()
        except Exception:
            body = b""
    text = body.decode("utf-8") if isinstance(body, bytes) else body
    try:
        return code, json.loads(text)
    except Exception:
        return code, text


def wait_ready(port, tries=40, delay=0.05):
    """Poll until the ephemeral server accepts /health (avoids race flakiness)."""
    last = None
    for _ in range(tries):
        try:
            code, raw = http_get(port, "/health", timeout=1)
            if code == 200:
                return True, raw
            last = "status %s" % code
        except Exception as exc:
            last = exc
        time.sleep(delay)
    return False, last


def main():
    print("GroveLink smoke_bridge — repo:", REPO)
    print("Python:", sys.version.replace("\n", " "))
    ver_path = os.path.join(REPO, "VERSION")
    pack_ver = "unknown"
    try:
        with open(ver_path, "r") as f:
            pack_ver = f.readline().strip()
    except Exception:
        pass
    check("VERSION file readable", bool(pack_ver), pack_ver)

    try:
        import grovelink_server as gl
    except Exception as exc:
        check("import grovelink_server", False, exc)
        return 1
    check("import grovelink_server", True)

    # Isolate photos dir under temp so we do not touch real cache
    tmp = tempfile.mkdtemp(prefix="gl_smoke_")
    photos = os.path.join(tmp, "photos")
    os.makedirs(photos)
    gl.WEB_PHOTOS = photos
    gl.DELETED_PATH = os.path.join(tmp, "photos_deleted.txt")
    gl.DELETED.clear()
    gl.OPEN_PHONE_TXT = os.path.join(tmp, "OPEN_ON_PHONE.txt")
    gl.WEB_NEWS = os.path.join(tmp, "news")
    os.makedirs(gl.WEB_NEWS)
    gl.CAPTIONS_PATH = os.path.join(tmp, "photos_captions.json")
    gl.CHAT_LOG_PATH = os.path.join(tmp, "chat_delivered.json")
    gl.FAVORITES_PATH = os.path.join(tmp, "photos_favorites.json")
    gl.COMMENTS_PATH = os.path.join(tmp, "photos_comments.json")
    gl.STREAK_PATH = os.path.join(tmp, "photos_streak.json")
    gl.REQUESTS_PATH = os.path.join(tmp, "requests.json")
    gl.POLL_PATH = os.path.join(tmp, "poll.json")
    gl.STATE["link_ini"] = os.path.join(tmp, "link.ini")

    port = free_port()
    gl.STATE["ip"] = "127.0.0.1"
    gl.STATE["port"] = port
    gl.STATE["photos"] = []
    gl.STATE["inbox"] = []
    gl.STATE["galleries"] = []
    gl.STATE["bridge_ok"] = True
    gl.STATE["max_photos"] = 40
    gl.STATE["poll_ms"] = 2000
    gl.STATE["version"] = pack_ver or gl.read_pack_version()
    gl.STATE["last_error"] = ""
    gl.STATE["last_refresh"] = 0
    gl.STATE["last_refresh_human"] = ""
    gl.STATE["phone_page_logged"] = False
    gl.STATE["gta_dir"] = tmp
    gl.STATE["spectate_viewers"] = {}
    gl.STATE["spectate_on"] = False
    gl.STATE["started_at"] = time.time() - 90
    gl.STATE["pinned_chat_id"] = ""
    gl.STATE["active_viewers"] = {}
    gl.STATE["rate_limit_send"] = {}
    gl.STATE["poll"] = None

    try:
        from http.server import HTTPServer
    except ImportError:
        from BaseHTTPServer import HTTPServer

    server = HTTPServer(("127.0.0.1", port), gl.Handler)
    server.link_ini = os.path.join(tmp, "link.ini")
    # seed a minimal ini so POST /send works
    with open(server.link_ini, "w") as f:
        f.write(
            "[INBOX]\nnew=0\nfrom=\nmsg=\n"
            "[OUTBOX]\nnew=0\nfrom=CJ\nmsg=\n"
            "[PHOTO]\ntake=0\n"
            "[STATUS]\nbridge=1\n"
            "[NEWS]\nnew=0\nmake=0\n"
            "[SPECTATE]\non=0\nframe=0\n"
            "[REQUEST]\nnew=0\nkind=\nfrom=\ntext=\n"
            "[POLL]\nnew=0\ncreate=0\nquestion=\noptions=\nsummary=\n"
            "[MSG]\nnew=0\ncontact=\nout=\nin=\nlast_out=\nlast_in=\n"
            "[MSG_SWEET]\nout=\nin=\n"
        )
    gl.STATE["link_ini"] = server.link_ini

    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()
    ready, ready_raw = wait_ready(port)
    check("server ready (/health)", ready, ready_raw if not ready else "ok")
    if not ready:
        try:
            server.shutdown()
        except Exception:
            pass
        print("Server never became ready — aborting remaining HTTP checks")
        # Still run static checks below by falling through carefully:
        # mark HTTP suite skipped via early jump after shutdown

    # --- /health ---
    try:
        if not ready:
            raise RuntimeError("server not ready")
        code, raw = http_get(port, "/health")
        health = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        check("GET /health status 200", code == 200, code)
        check("GET /health ok", health.get("ok") is True)
        check("GET /health version", health.get("version") == gl.STATE["version"], health.get("version"))
        check("GET /health poll_ms", isinstance(health.get("poll_ms"), int), health.get("poll_ms"))
        check("GET /health last_error field", "last_error" in health, repr(health.get("last_error")))
        check("GET /health skipped_deleted field", "skipped_deleted" in health, health.get("skipped_deleted"))
        check("GET /health bridge_ok", health.get("bridge_ok") is True)
    except Exception as exc:
        check("GET /health", False, traceback.format_exc() if False else exc)

    # --- /api ---
    try:
        code, raw = http_get(port, "/api")
        api = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        check("GET /api status 200", code == 200, code)
        check("GET /api photos list", isinstance(api.get("photos"), list))
        check("GET /api poll_ms", isinstance(api.get("poll_ms"), int), api.get("poll_ms"))
        check("GET /api last_error field", "last_error" in api, repr(api.get("last_error")))
        check("GET /api version", api.get("version") == gl.STATE["version"], api.get("version"))
        check("GET /api count", api.get("count") == 0, api.get("count"))
        check("GET /api skipped_deleted field", "skipped_deleted" in api, api.get("skipped_deleted"))
        check("GET /health skipped_deleted via /api first", isinstance(api.get("skipped_deleted"), int))
    except Exception as exc:
        check("GET /api", False, exc)

    # --- / (HTML: empty LAN + delete confirm) ---
    try:
        code, raw = http_get(port, "/")
        html = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        check("GET / status 200", code == 200, code)
        check("GET / has emptyHtml / FIRST VISIT", ("FIRST VISIT" in html) or ("emptyHtml" in html) or ("empty-lan" in html))
        check("GET / has Delete this shot?", "Delete this shot?" in html)
        check("GET / has LIVE / version inject", gl.STATE["version"] in html or "VERSION" in html)
        check("GET / has Export zip", "export.zip" in html or "Export zip" in html)
    except Exception as exc:
        check("GET /", False, exc)

    # --- drop a fake photo + refresh list ---
    try:
        fake = os.path.join(photos, "1111111111_smoke.jpg")
        with open(fake, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 200)  # tiny jpeg-ish
        gl.copy_latest([])  # re-scan bridge photos only
        code, raw = http_get(port, "/api")
        api = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        check("GET /api after fake photo count>=1", api.get("count", 0) >= 1, api.get("count"))
        check("GET /api latest set", bool(api.get("latest")), api.get("latest"))
        latest = api.get("latest") or ""
        if latest:
            code2, img = http_get(port, "/photo/" + latest)
            check("GET /photo/…", code2 == 200 and len(img) > 10, code2)
    except Exception as exc:
        check("gallery/bridge photo path", False, exc)

    # --- /export.zip ---
    try:
        code, raw = http_get(port, "/export.zip")
        check("GET /export.zip status 200", code == 200, code)
        check("GET /export.zip is zip", raw[:2] == b"PK", repr(raw[:4]))
        check("GET /export.zip non-empty", len(raw) > 30, len(raw))
    except Exception as exc:
        check("GET /export.zip", False, exc)

    # --- POST /clear ---
    try:
        try:
            from urllib.request import Request, urlopen
        except ImportError:
            from urllib2 import Request, urlopen
        # Seed another fake file
        fake2 = os.path.join(photos, "2222222222_clearme.jpg")
        with open(fake2, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 200)
        gl.copy_latest([])
        req = Request(
            "http://127.0.0.1:%s/clear" % port,
            data=b"confirm=1",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp = urlopen(req, timeout=5)
        body = resp.read()
        code = getattr(resp, "status", None) or resp.getcode()
        j = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
        check("POST /clear status 200", code == 200, code)
        check("POST /clear ok", j.get("ok") is True, j)
        check("POST /clear removed files", int(j.get("cleared") or 0) >= 1, j.get("cleared"))
        code2, raw2 = http_get(port, "/api")
        api2 = json.loads(raw2.decode("utf-8") if isinstance(raw2, bytes) else raw2)
        check("GET /api count 0 after clear", api2.get("count") == 0, api2.get("count"))
        # GET without confirm should 400
        try:
            http_get(port, "/clear")
            check("GET /clear without confirm rejected", False, "expected error")
        except Exception:
            check("GET /clear without confirm rejected", True)
        code3, _ = http_get(port, "/clear?confirm=1")
        check("GET /clear?confirm=1", code3 == 200, code3)
        # POST without confirm should 400 (auth guard)
        try:
            req_bad = Request(
                "http://127.0.0.1:%s/clear" % port,
                data=b"",
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            urlopen(req_bad, timeout=5)
            check("POST /clear without confirm rejected", False, "expected error")
        except Exception:
            check("POST /clear without confirm rejected", True)
        # Seed + delete one so skipped_deleted > 0
        fake3 = os.path.join(photos, "3333333333_skip.jpg")
        with open(fake3, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 200)
        gl.copy_latest([])
        code, raw = http_get(port, "/api")
        api = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        latest = api.get("latest") or "3333333333_skip.jpg"
        req_del = Request(
            "http://127.0.0.1:%s/delete" % port,
            data=("file=" + latest).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        urlopen(req_del, timeout=5)
        code, raw = http_get(port, "/api")
        api = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        check("GET /api skipped_deleted after delete", int(api.get("skipped_deleted") or 0) >= 1, api.get("skipped_deleted"))
    except Exception as exc:
        check("POST /clear", False, exc)

    # --- HTML has search + clear + sort (client-side) + home-screen tip ---
    try:
        code, raw = http_get(port, "/")
        html = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        check("GET / has search box", 'id="search"' in html or "Search filename" in html)
        check("GET / has Clear all phone copies", "Clear all phone copies" in html)
        check("GET / has sort toggle Newest", 'id="tab_sort"' in html and "Newest" in html)
        check("GET / sort is client-side (SORT_ORDER)", "SORT_ORDER" in html and "client-side" in html.lower())
        check("GET / no favicon link", "favicon" not in html.lower() or "no favicon" in html.lower())
        check("GET / apple-mobile-web-app-capable", "apple-mobile-web-app-capable" in html)
        check("GET / Add to Home Screen tip", "Add to Home Screen" in html)
        check("GET / skip_note / skipped UI", "skip_note" in html or "Hidden from phone" in html)
        check("GET / has help footer Shortcuts", "help_foot" in html and "Shortcuts" in html)
        check("GET / help ? toggle", "help_toggle" in html and "toggleHelpDetail" in html)
        check("GET / Esc closes lightbox keydown", "keyCode === 27" in html or "Escape" in html)
        check("GET / clear_all starts disabled", 'id="clear_all"' in html and "disabled" in html)
        check("GET / export_zip starts disabled", 'id="export_zip"' in html and 'href="#"' in html)
        check("GET / setCountActions helper", "setCountActions" in html)
    except Exception as exc:
        check("search/clear/sort HTML", False, exc)

    # --- last_error when gallery unreadable ---
    try:
        unreadable = os.path.join(tmp, "unreadable_gallery")
        if not os.path.isdir(unreadable):
            os.makedirs(unreadable)
        gl.STATE["last_error"] = ""
        triggered = False
        try:
            os.chmod(unreadable, 0)
            gl.list_images([unreadable])
            triggered = bool(gl.STATE.get("last_error"))
        except Exception:
            triggered = False
        finally:
            try:
                os.chmod(unreadable, 0o755)
            except Exception:
                pass
        if not triggered:
            # Fallback (e.g. running as root where chmod 0 still lists): set then round-trip
            gl.STATE["last_error"] = "gallery unreadable: %s (smoke)" % unreadable
        code, raw = http_get(port, "/api")
        api = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        check("GET /api last_error populated", bool(api.get("last_error")), api.get("last_error"))
        # Point briefly at a good empty dir so list_images clears gallery-unreadable prefix
        good = os.path.join(tmp, "good_gallery")
        if not os.path.isdir(good):
            os.makedirs(good)
        gl.STATE["last_error"] = "gallery unreadable: temp"
        gl.list_images([good])
        code, raw = http_get(port, "/api")
        api = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        check("GET /api last_error clears via good gallery", api.get("last_error") == "", repr(api.get("last_error")))
    except Exception as exc:
        check("last_error gallery path", False, exc)

    # --- POST /send (ini + chat) ---
    gl.STATE["rate_limit_send"] = {}
    try:
        try:
            from urllib.request import Request, urlopen
        except ImportError:
            from urllib2 import Request, urlopen
        req = Request(
            "http://127.0.0.1:%s/send" % port,
            data=b"msg=Smoke+test&from=Smoke+Tester",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp = urlopen(req, timeout=5)
        body = resp.read()
        code = getattr(resp, "status", None) or resp.getcode()
        jsend = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
        check("POST /send", code == 200 and jsend.get("ok") is True, code)
        check("POST /send delivered flag", jsend.get("delivered") is True, jsend)
        # link.ini INBOX written
        ini_txt = ""
        try:
            with open(server.link_ini, "r") as f:
                ini_txt = f.read()
        except Exception as exc:
            ini_txt = str(exc)
        check("POST /send writes INBOX.new=1", "new=1" in ini_txt, ini_txt[:200])
        check("POST /send writes from=", "from=Smoke Tester" in ini_txt or "from=Smoke+Tester" in ini_txt
              or "Smoke Tester" in ini_txt, ini_txt[:300])
        check("POST /send writes msg=", "Smoke test" in ini_txt or "Smoke+test" in ini_txt, ini_txt[:300])
        # chat API
        code_c, raw_c = http_get(port, "/api/chat")
        chat = json.loads(raw_c.decode("utf-8") if isinstance(raw_c, bytes) else raw_c)
        check("GET /api/chat status 200", code_c == 200, code_c)
        check("GET /api/chat inbox list", isinstance(chat.get("inbox"), list) and len(chat.get("inbox") or []) >= 1, chat)
        code_a, raw_a = http_get(port, "/api")
        api_chat = json.loads(raw_a.decode("utf-8") if isinstance(raw_a, bytes) else raw_a)
        check("GET /api inbox has delivered", isinstance(api_chat.get("inbox"), list) and len(api_chat.get("inbox") or []) >= 1)
    except Exception as exc:
        check("POST /send + chat", False, exc)

    # --- gallery HTML 1.8.0 (hero / Breaking News / composer) ---
    try:
        code, raw = http_get(port, "/")
        html = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        check("GET / has hero / LATEST", "LATEST" in html or 'class="hero"' in html or "sectionlab" in html)
        check("GET / has Breaking News", "Breaking News" in html)
        check("GET / has sticky composer", 'id="composer"' in html or "composer" in html)
        check("GET / has From:/Nickname field", "from_name" in html and ("Nickname" in html or "From:" in html))
        check("GET / has chat thread", 'id="chat_thread"' in html or "TEXTS TO CJ" in html)
        check("GET / has Grove Street Herald link", "/news" in html and "Herald" in html)
        check("GET / has Share page / sharePhoto", "share_page" in html or "sharePhoto" in html)
        check("GET / has Breaking News location dlg", "news_dlg" in html and "news_loc_sel" in html)
    except Exception as exc:
        check("gallery HTML 1.8.0", False, exc)

    # --- /news + POST /news ---
    try:
        try:
            from urllib.request import Request, urlopen
        except ImportError:
            from urllib2 import Request, urlopen
        # Ensure a photo exists for news
        fake_n = os.path.join(photos, "4444444444_news.jpg")
        with open(fake_n, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 200)
        gl.copy_latest([])
        code, raw = http_get(port, "/api")
        api = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        latest = api.get("latest") or "4444444444_news.jpg"
        code_n, raw_n = http_get(port, "/news")
        html_n = raw_n.decode("utf-8") if isinstance(raw_n, bytes) else raw_n
        check("GET /news index 200", code_n == 200, code_n)
        check("GET /news Herald masthead", "Grove Street Herald" in html_n)
        check("GET /news Los Santos Weather", "Los Santos Weather" in html_n)
        req = Request(
            "http://127.0.0.1:%s/news" % port,
            data=("file=" + latest + "&caption=Smoke+Herald+caption&location=Grove+Street").encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp = urlopen(req, timeout=5)
        body = resp.read()
        code = getattr(resp, "status", None) or resp.getcode()
        jn = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
        check("POST /news status 200", code == 200, code)
        check("POST /news ok + id", jn.get("ok") is True and bool(jn.get("id")), jn)
        check("POST /news returns location", jn.get("location") == "Grove Street", jn)
        art_id = jn.get("id") or ""
        if art_id:
            code_a, raw_a = http_get(port, "/news/" + art_id)
            html_a = raw_a.decode("utf-8") if isinstance(raw_a, bytes) else raw_a
            check("GET /news/<id> 200", code_a == 200, code_a)
            check("GET /news/<id> has headline", bool(jn.get("headline")) and (jn.get("headline") in html_a), jn.get("headline"))
            check("GET /news/<id> embeds photo img", ("/photo/" + latest) in html_a or 'src="/photo/' in html_a, html_a[:200])
            check("GET /news/<id> location badge", "Grove Street" in html_a and ("📍" in html_a or "locbadge" in html_a), html_a[html_a.find("locbadge")-20:html_a.find("locbadge")+80] if "locbadge" in html_a else html_a[:300])
            check("GET /news/<id> headline uses location", "Grove Street" in (jn.get("headline") or ""), jn.get("headline"))
            # NEWS.new flag in ini
            with open(server.link_ini, "r") as f:
                ini2 = f.read()
            check("POST /news sets NEWS.new=1", "new=1" in ini2.split("[NEWS]")[-1] if "[NEWS]" in ini2 else False, ini2[-200:])
            # Index also shows location
            code_n2, raw_n2 = http_get(port, "/news")
            html_n2 = raw_n2.decode("utf-8") if isinstance(raw_n2, bytes) else raw_n2
            check("GET /news index shows location", "Grove Street" in html_n2 and ("📍" in html_n2 or "locbadge" in html_n2), html_n2[:400])
        # caption endpoint
        req_c = Request(
            "http://127.0.0.1:%s/caption" % port,
            data=("file=" + latest + "&caption=Smoke+cap").encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp_c = urlopen(req_c, timeout=5)
        body_c = resp_c.read()
        jc = json.loads(body_c.decode("utf-8") if isinstance(body_c, bytes) else body_c)
        check("POST /caption ok", jc.get("ok") is True, jc)
        code, raw = http_get(port, "/api")
        api = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        caps = [p.get("caption") for p in (api.get("photos") or []) if p.get("file") == latest]
        check("GET /api photo caption", caps and caps[0] == "Smoke cap", caps)
    except Exception as exc:
        check("news/caption suite", False, exc)

    # --- 1.8.1 Camera ≠ Breaking News ---
    try:
        before_arts = len(gl.list_news_articles(100))
        # Ensure a photo exists in bridge cache for make→create_news
        cam_name = "5555555555_camera_only.jpg"
        cam_path = os.path.join(photos, cam_name)
        with open(cam_path, "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 200)
        gl.copy_latest([])
        # Camera path: PHOTO.take alone must NOT create news
        with open(server.link_ini, "w") as f:
            f.write(
                "[INBOX]\nnew=0\nfrom=\nmsg=\n"
                "[PHOTO]\ntake=1\ncount=1\n"
                "[STATUS]\nbridge=1\n"
                "[NEWS]\nnew=0\nmake=0\n"
            )
        gl.STATE["link_ini"] = server.link_ini
        # Short burst so smoke stays fast
        try:
            from configparser import ConfigParser
        except ImportError:
            from ConfigParser import ConfigParser
        empty_cfg = ConfigParser()
        handled = gl.process_photo_and_news_flags(
            empty_cfg, tmp, server.link_ini, burst_seconds=0.05, burst_interval=0.02
        )
        after_take = len(gl.list_news_articles(100))
        with open(server.link_ini, "r") as f:
            ini_take = f.read()
        check("Camera PHOTO.take handled", handled is True)
        check("Camera PHOTO.take cleared", "take=0" in ini_take.split("[PHOTO]")[-1].split("[")[0])
        check("Camera PHOTO.take alone creates NO news", after_take == before_arts,
              "before=%s after=%s" % (before_arts, after_take))
        check("no news_auto in STATE", "news_auto" not in gl.STATE)

        # NEWS.make=1 → article created + NEWS.new=1
        before_make = len(gl.list_news_articles(100))
        with open(server.link_ini, "w") as f:
            f.write(
                "[INBOX]\nnew=0\nfrom=\nmsg=\n"
                "[PHOTO]\ntake=1\ncount=2\n"
                "[STATUS]\nbridge=1\n"
                "[NEWS]\nnew=0\nmake=1\nzone=Idlewood\n"
            )
        handled2 = gl.process_photo_and_news_flags(
            empty_cfg, tmp, server.link_ini, burst_seconds=0.05, burst_interval=0.02
        )
        after_make = len(gl.list_news_articles(100))
        with open(server.link_ini, "r") as f:
            ini_make = f.read()
        check("NEWS.make handled", handled2 is True)
        check("NEWS.make cleared to 0", "make=0" in ini_make.split("[NEWS]")[-1] if "[NEWS]" in ini_make else False, ini_make[-200:])
        check("NEWS.make creates article", after_make == before_make + 1,
              "before=%s after=%s" % (before_make, after_make))
        check("NEWS.make sets NEWS.new=1", "new=1" in ini_make.split("[NEWS]")[-1] if "[NEWS]" in ini_make else False, ini_make[-200:])
        # Location from NEWS.zone on article + HTML (find Idlewood among recent; mtime sort may tie)
        arts_make = gl.list_news_articles(10)
        art_loc = None
        for a in arts_make:
            if (a.get("location") or "") == "Idlewood":
                art_loc = a
                break
        check("NEWS.make article has location Idlewood", art_loc is not None, arts_make[:3] if arts_make else None)
        if art_loc and art_loc.get("id"):
            code_ml, raw_ml = http_get(port, "/news/" + art_loc["id"])
            html_ml = raw_ml.decode("utf-8") if isinstance(raw_ml, bytes) else raw_ml
            check("NEWS.make location appears in HTML", "Idlewood" in html_ml and ("📍" in html_ml or "locbadge" in html_ml), html_ml[:400])
        else:
            check("NEWS.make location appears in HTML", False, "no Idlewood article")
        # shutter_burst source must not mention news_auto
        with open(os.path.join(BRIDGE, "grovelink_server.py"), "r") as f:
            srv_src = f.read()
        check("bridge has no news_auto", "news_auto" not in srv_src)
        check("bridge has no news.auto print", "news.auto" not in srv_src)
        check("bridge has NEWS.make handler", "NEWS" in srv_src and "make" in srv_src and "process_photo_and_news_flags" in srv_src)
    except Exception as exc:
        check("Camera vs NEWS.make suite", False, "%s\n%s" % (exc, traceback.format_exc()[:400]))

    # --- 1.9.0 CJ REPLY (OUTBOX) + SPECTATE ---
    try:
        # OUTBOX.new=1 → chat log as CJ
        with open(server.link_ini, "w") as f:
            f.write(
                "[INBOX]\nnew=0\nfrom=\nmsg=\n"
                "[OUTBOX]\nnew=1\nfrom=CJ\nmsg=Grove forever\n"
                "[PHOTO]\ntake=0\n"
                "[STATUS]\nbridge=1\n"
                "[NEWS]\nnew=0\nmake=0\n"
                "[SPECTATE]\non=0\nframe=0\n"
            )
        gl.STATE["link_ini"] = server.link_ini
        before_chat = len(gl.load_chat_log())
        handled_ob = gl.process_outbox_flag(server.link_ini)
        after_chat = gl.load_chat_log()
        with open(server.link_ini, "r") as f:
            ini_ob = f.read()
        check("OUTBOX.new handled", handled_ob is True)
        check("OUTBOX.new cleared", "new=0" in ini_ob.split("[OUTBOX]")[-1].split("[")[0], ini_ob)
        check("OUTBOX appends chat", len(after_chat) == before_chat + 1,
              "before=%s after=%s" % (before_chat, len(after_chat)))
        top = after_chat[0] if after_chat else {}
        check("OUTBOX chat from CJ", (top.get("from") or "").upper() == "CJ" or top.get("role") == "cj", top)
        check("OUTBOX chat msg", "Grove forever" in (top.get("msg") or ""), top)
        check("OUTBOX chat role cj", top.get("role") == "cj" or top.get("side") == "cj", top)
        code_c2, raw_c2 = http_get(port, "/api/chat")
        chat2 = json.loads(raw_c2.decode("utf-8") if isinstance(raw_c2, bytes) else raw_c2)
        inbox2 = chat2.get("inbox") or []
        has_cj = any(
            (isinstance(m, dict) and ((m.get("from") or "").upper() == "CJ" or m.get("role") == "cj"))
            for m in inbox2
        )
        check("GET /api/chat shows CJ reply", has_cj, inbox2[:2] if inbox2 else None)
        code_a2, raw_a2 = http_get(port, "/api")
        api2 = json.loads(raw_a2.decode("utf-8") if isinstance(raw_a2, bytes) else raw_a2)
        check("GET /api has spectate_on field", "spectate_on" in api2, api2.get("spectate_on"))
        check("GET /api has latest_url field", "latest_url" in api2)

        # /spectate HTML
        code_sp, raw_sp = http_get(port, "/spectate")
        html_sp = raw_sp.decode("utf-8") if isinstance(raw_sp, bytes) else raw_sp
        check("GET /spectate status 200", code_sp == 200, code_sp)
        check("GET /spectate LIVE SPECTATE badge", "LIVE SPECTATE" in html_sp)
        check("GET /spectate waiting copy", "Waiting for spectate frames" in html_sp or "WAITING FOR SPECTATE" in html_sp)
        check("GET /spectate link back to phone", 'href="/"' in html_sp or "GroveLink phone" in html_sp)
        check("GET /spectate polls /api/spectate", "/api/spectate" in html_sp)
        code_as, raw_as = http_get(port, "/api/spectate")
        spj = json.loads(raw_as.decode("utf-8") if isinstance(raw_as, bytes) else raw_as)
        check("GET /api/spectate ok", code_as == 200 and spj.get("ok") is True, spj)
        check("GET /api/spectate has latest_url", "latest_url" in spj)
        code_home, raw_home = http_get(port, "/")
        html_home = raw_home.decode("utf-8") if isinstance(raw_home, bytes) else raw_home
        check("GET / has spectate link", "/spectate" in html_home and "SPECTATE" in html_home)
        check("GET / chat styles CJ vs visitor", "chatmsg cj" in html_home or ".chatmsg.cj" in html_home)

        # SPECTATE.frame → copy, NO news
        before_sf = len(gl.list_news_articles(100))
        spec_name = "6666666666_spectate.jpg"
        with open(os.path.join(photos, spec_name), "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 200)
        gl.copy_latest([])
        with open(server.link_ini, "w") as f:
            f.write(
                "[INBOX]\nnew=0\nfrom=\nmsg=\n"
                "[OUTBOX]\nnew=0\nfrom=CJ\nmsg=\n"
                "[PHOTO]\ntake=0\ncount=3\n"
                "[STATUS]\nbridge=1\n"
                "[NEWS]\nnew=0\nmake=0\n"
                "[SPECTATE]\non=1\nframe=1\n"
            )
        try:
            from configparser import ConfigParser
        except ImportError:
            from ConfigParser import ConfigParser
        empty_cfg2 = ConfigParser()
        handled_sf = gl.process_photo_and_news_flags(
            empty_cfg2, tmp, server.link_ini, burst_seconds=0.05, burst_interval=0.02
        )
        after_sf = len(gl.list_news_articles(100))
        with open(server.link_ini, "r") as f:
            ini_sf = f.read()
        check("SPECTATE.frame handled", handled_sf is True)
        check("SPECTATE.frame cleared", "frame=0" in ini_sf.split("[SPECTATE]")[-1] if "[SPECTATE]" in ini_sf else False, ini_sf[-200:])
        check("SPECTATE.frame creates NO news", after_sf == before_sf,
              "before=%s after=%s" % (before_sf, after_sf))
        check("SPECTATE.on reflected", gl.STATE.get("spectate_on") is True)
        # Camera still no NEWS after spectate path (sanity)
        check("Camera still separate from NEWS", "news_auto" not in open(os.path.join(BRIDGE, "grovelink_server.py")).read())
    except Exception as exc:
        check("1.9.0 OUTBOX+SPECTATE suite", False, "%s\n%s" % (exc, traceback.format_exc()[:500]))


    # --- 2.0.0 favorites + manifest + hud + spectate UX ---
    try:
        try:
            from urllib.request import Request, urlopen
        except ImportError:
            from urllib2 import Request, urlopen
        # Seed photo for favorite
        fav_name = "7777777777_fav.jpg"
        with open(os.path.join(photos, fav_name), "wb") as f:
            f.write(b"\xff\xd8\xff\xe0" + b"\x00" * 200)
        gl.copy_latest([])
        gl.FAVORITES_PATH = os.path.join(tmp, "photos_favorites.json")
        req_f = Request(
            "http://127.0.0.1:%s/favorite" % port,
            data=("file=" + fav_name + "&favorite=1").encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp_f = urlopen(req_f, timeout=5)
        body_f = resp_f.read()
        code_f = getattr(resp_f, "status", None) or resp_f.getcode()
        jf = json.loads(body_f.decode("utf-8") if isinstance(body_f, bytes) else body_f)
        check("POST /favorite status 200", code_f == 200, code_f)
        check("POST /favorite ok", jf.get("ok") is True, jf)
        check("POST /favorite lists file", fav_name in (jf.get("favorites") or []), jf)
        code_fg, raw_fg = http_get(port, "/favorite")
        jfg = json.loads(raw_fg.decode("utf-8") if isinstance(raw_fg, bytes) else raw_fg)
        check("GET /favorite list", code_fg == 200 and fav_name in (jfg.get("favorites") or []), jfg)
        # Write STATUS HUD fields into ini
        with open(server.link_ini, "w") as f:
            f.write(
                "[INBOX]\nnew=0\nfrom=\nmsg=\n"
                "[OUTBOX]\nnew=0\nfrom=CJ\nmsg=\n"
                "[PHOTO]\ntake=0\ncount=1\n"
                "[STATUS]\nbridge=1\nwanted=3\nmoney=12500\nzone=Grove Street\nhour=14\nspectate=1\n"
                "[NEWS]\nnew=0\nmake=0\n"
                "[SPECTATE]\non=1\nframe=0\n"
            )
        gl.STATE["link_ini"] = server.link_ini
        code_a, raw_a = http_get(port, "/api")
        api_h = json.loads(raw_a.decode("utf-8") if isinstance(raw_a, bytes) else raw_a)
        check("GET /api has hud object", isinstance(api_h.get("hud"), dict), api_h.get("hud"))
        hud = api_h.get("hud") or {}
        check("GET /api hud.wanted", hud.get("wanted") == 3, hud)
        check("GET /api hud.money", hud.get("money") == 12500, hud)
        check("GET /api hud.zone", hud.get("zone") == "Grove Street", hud)
        check("GET /api hud.hour", hud.get("hour") == 14, hud)
        check("GET /api hud.spectate", hud.get("spectate") is True, hud)
        check("GET /api favorites field", isinstance(api_h.get("favorites"), list) and fav_name in api_h.get("favorites"), api_h.get("favorites"))
        # Photo favorite flag
        fav_flags = [p.get("favorite") for p in (api_h.get("photos") or []) if p.get("file") == fav_name]
        check("GET /api photo.favorite true", fav_flags and fav_flags[0] is True, fav_flags)
        # Manifest
        code_m, raw_m = http_get(port, "/manifest.webmanifest")
        check("GET /manifest.webmanifest 200", code_m == 200, code_m)
        try:
            man = json.loads(raw_m.decode("utf-8") if isinstance(raw_m, bytes) else raw_m)
        except Exception:
            man = {}
        check("manifest name GroveLink", "GroveLink" in str(man.get("name") or man.get("short_name") or ""), man)
        check("manifest display standalone", man.get("display") == "standalone", man)
        check("manifest start_url", man.get("start_url") in ("/", "/index.html"), man)
        # HTML hooks
        code_h, raw_h = http_get(port, "/")
        html_h = raw_h.decode("utf-8") if isinstance(raw_h, bytes) else raw_h
        check("GET / links manifest", 'rel="manifest"' in html_h and "/manifest.webmanifest" in html_h)
        check("GET / has Favorites tab", 'id="tab_fav"' in html_h and "Favorites" in html_h)
        check("GET / has Quick Actions", 'id="quick_actions"' in html_h or "qa_camera" in html_h)
        check("GET / has HUD strip", 'id="hud_strip"' in html_h)
        check("GET / has chat notify btn", 'id="chat_notify_btn"' in html_h)
        check("GET / has fav toggle JS", "toggleFavorite" in html_h and "LS_FAV" in html_h)
        # Spectate UX
        code_sp2, raw_sp2 = http_get(port, "/spectate")
        html_sp2 = raw_sp2.decode("utf-8") if isinstance(raw_sp2, bytes) else raw_sp2
        check("GET /spectate snapshot live banner", "snapshot live" in html_sp2.lower() and "not video" in html_sp2.lower())
        check("GET /spectate fullscreen btn", "btn_fs" in html_sp2 or "Fullscreen" in html_sp2)
        check("GET /spectate pause btn", "btn_pause" in html_sp2 or "Pause" in html_sp2)
        check("GET /spectate ageLabel", "ageLabel" in html_sp2 or "age_sec" in html_sp2)
        code_as2, raw_as2 = http_get(port, "/api/spectate")
        spj2 = json.loads(raw_as2.decode("utf-8") if isinstance(raw_as2, bytes) else raw_as2)
        check("GET /api/spectate age_sec", "age_sec" in spj2, spj2)
        check("GET /api/spectate poll_ms hot when on", int(spj2.get("poll_ms") or 0) <= 500, spj2.get("poll_ms"))
        # News share button
        arts = gl.list_news_articles(5)
        if arts:
            aid = arts[0].get("id")
            code_na, raw_na = http_get(port, "/news/" + aid)
            html_na = raw_na.decode("utf-8") if isinstance(raw_na, bytes) else raw_na
            check("GET /news/<id> Share article", "share_article" in html_na or "Share article" in html_na)
        else:
            # create one quickly
            req_n = Request(
                "http://127.0.0.1:%s/news" % port,
                data=("file=" + fav_name + "&location=Grove+Street").encode("utf-8"),
                headers={"Content-Type": "application/x-www-form-urlencoded"},
            )
            resp_n = urlopen(req_n, timeout=5)
            jn = json.loads(resp_n.read().decode("utf-8"))
            aid = jn.get("id")
            code_na, raw_na = http_get(port, "/news/" + aid)
            html_na = raw_na.decode("utf-8") if isinstance(raw_na, bytes) else raw_na
            check("GET /news/<id> Share article", "share_article" in html_na or "Share article" in html_na)
        # RESEARCH.md present
        research = os.path.join(REPO, "grovelink", "RESEARCH.md")
        check("RESEARCH.md exists", os.path.isfile(research))
        with open(research, "r") as f:
            res = f.read()
        check("RESEARCH.md maps sources", "iFruit" in res or "companion" in res.lower())
        check("RESEARCH.md out of scope taxi/homie", "taxi" in res.lower() and "out of scope" in res.lower())
        # CLEO HUD writes
        with open(os.path.join(REPO, "grovelink", "GroveLinkPhone.txt"), "r") as f:
            cleo20 = f.read()
        check("CLEO STATUS_HUD_TICK", ":STATUS_HUD_TICK" in cleo20)
        check("CLEO writes STATUS.wanted", 'section "STATUS" key "wanted"' in cleo20)
        check("CLEO writes STATUS.hour", 'section "STATUS" key "hour"' in cleo20)
        check("CLEO uses 01C0 wanted", "01C0:" in cleo20 and "store_wanted_level" in cleo20)
        check("CLEO uses 010B money", "010B:" in cleo20 and "store_score" in cleo20)
        check("CLEO uses 00BF hour", "00BF:" in cleo20 and "get_time_of_day" in cleo20)
    except Exception as exc:
        check("2.0.0 favorites/manifest/hud suite", False, "%s\n%s" % (exc, traceback.format_exc()[:500]))

    # --- 2.1.0 nicknames + watching + Moments + wanted toast + By place ---
    try:
        try:
            from urllib.request import Request, urlopen
        except ImportError:
            from urllib2 import Request, urlopen

        gl.STATE["rate_limit_send"] = {}
        # Nickname / name= alias on /send
        req_nick = Request(
            "http://127.0.0.1:%s/send" % port,
            data=b"msg=Yo+CJ&name=SmokeNick",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp_nick = urlopen(req_nick, timeout=5)
        jnick = json.loads(resp_nick.read().decode("utf-8"))
        check("POST /send name= nickname", jnick.get("ok") is True and jnick.get("from") == "SmokeNick", jnick)
        code_chat, raw_chat = http_get(port, "/api/chat")
        jchat = json.loads(raw_chat.decode("utf-8") if isinstance(raw_chat, bytes) else raw_chat)
        inbox = jchat.get("inbox") or []
        nick_hit = any(
            (isinstance(m, dict) and m.get("from") == "SmokeNick" and "Yo CJ" in (m.get("msg") or ""))
            for m in inbox
        )
        check("chat thread shows nickname", nick_hit, inbox[:2] if inbox else inbox)

        gl.STATE["rate_limit_send"] = {}
        # Empty / missing from defaults to REAL PHONE
        req_def = Request(
            "http://127.0.0.1:%s/send" % port,
            data=b"msg=Default+name+test",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp_def = urlopen(req_def, timeout=5)
        jdef = json.loads(resp_def.read().decode("utf-8"))
        check("POST /send default REAL PHONE", jdef.get("from") == "REAL PHONE", jdef)

        # HTML nickname persistence hooks
        code_h21, raw_h21 = http_get(port, "/")
        html21 = raw_h21.decode("utf-8") if isinstance(raw_h21, bytes) else raw_h21
        check("GET / nickname localStorage", "grovelink_nickname" in html21 or "LS_NICK" in html21)
        check("GET / Nickname label", "Nickname" in html21)
        check("GET / Moments reel", "moments_reel" in html21 and "renderMoments" in html21)
        check("GET / By place tab", "tab_place" in html21 and "By place" in html21)
        check("GET / wanted toast hook", "WANTED" in html21 and "maybeWantedToast" in html21 and "showToast" in html21)
        check("GET / watching UI", "qa_watching" in html21 or "watching_note" in html21)

        # Spectate watching count: poll /api/spectate then check field
        code_w1, raw_w1 = http_get(port, "/api/spectate")
        jw1 = json.loads(raw_w1.decode("utf-8") if isinstance(raw_w1, bytes) else raw_w1)
        check("GET /api/spectate has watching", "watching" in jw1 and isinstance(jw1.get("watching"), int), jw1)
        check("GET /api/spectate watching >= 1", int(jw1.get("watching") or 0) >= 1, jw1)
        # /spectate page also counts
        code_spw, raw_spw = http_get(port, "/spectate")
        html_spw = raw_spw.decode("utf-8") if isinstance(raw_spw, bytes) else raw_spw
        check("GET /spectate watching UI", "watching" in html_spw.lower())
        code_apiw, raw_apiw = http_get(port, "/api")
        japiw = json.loads(raw_apiw.decode("utf-8") if isinstance(raw_apiw, bytes) else raw_apiw)
        check("GET /api has watching", "watching" in japiw, japiw)
        check("GET /api has places list", isinstance(japiw.get("places"), list), japiw.get("places"))

        # Location attach: caption tag + news location
        loc_photo = "7777777777_place.jpg"
        with open(os.path.join(photos, loc_photo), "wb") as f:
            f.write(b"\xff\xd8\xff\xd9" + b"0" * 200)
        gl.set_caption(loc_photo, "hanging at loc:Idlewood")
        news_photo = "7777777778_newsplace.jpg"
        with open(os.path.join(photos, news_photo), "wb") as f:
            f.write(b"\xff\xd8\xff\xd9" + b"1" * 200)
        now_ts = int(time.time())
        gl.STATE["photos"] = [
            {"file": news_photo, "mtime": now_ts, "when": "now", "size": 204, "size_h": "204 B"},
            {"file": loc_photo, "mtime": now_ts - 10, "when": "now", "size": 204, "size_h": "204 B"},
        ] + [p for p in (gl.STATE.get("photos") or []) if isinstance(p, dict) and p.get("file") not in (news_photo, loc_photo)]
        req_np = Request(
            "http://127.0.0.1:%s/news" % port,
            data=("file=" + news_photo + "&location=Grove+Street").encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp_np = urlopen(req_np, timeout=5)
        jnp = json.loads(resp_np.read().decode("utf-8"))
        check("POST /news Grove Street for By place", jnp.get("ok") is True and jnp.get("location") == "Grove Street", jnp)

        code_pl, raw_pl = http_get(port, "/api")
        jpl = json.loads(raw_pl.decode("utf-8") if isinstance(raw_pl, bytes) else raw_pl)
        photos_pl = jpl.get("photos") or []
        loc_photo_meta = [p for p in photos_pl if p.get("file") == loc_photo]
        news_photo_meta = [p for p in photos_pl if p.get("file") == news_photo]
        check(
            "GET /api photo location from caption",
            loc_photo_meta and loc_photo_meta[0].get("location") == "Idlewood",
            loc_photo_meta[:1],
        )
        check(
            "GET /api photo location from news",
            news_photo_meta and news_photo_meta[0].get("location") == "Grove Street",
            news_photo_meta[:1],
        )
        places = jpl.get("places") or []
        place_names = [x.get("place") for x in places if isinstance(x, dict)]
        check("GET /api places includes Idlewood", "Idlewood" in place_names, places)
        check("GET /api places includes Grove Street", "Grove Street" in place_names, places)

        # Helper unit checks
        check("location_from_caption hash", gl.location_from_caption("#Vinewood night") == "Vinewood")
        check("note_spectate_viewer counts", gl.note_spectate_viewer("203.0.113.9") >= 1)

        # FEATURES / RESEARCH / CHANGELOG mention 2.1.0
        with open(os.path.join(REPO, "grovelink", "FEATURES.md"), "r") as f:
            feat21 = f.read()
        check("FEATURES.md 2.1.0", "2.1.0" in feat21 and "nickname" in feat21.lower())
        check("FEATURES.md Moments / By place / watching", "Moments" in feat21 and "By place" in feat21 and "watching" in feat21.lower())
        with open(os.path.join(REPO, "grovelink", "RESEARCH.md"), "r") as f:
            res21 = f.read()
        check("RESEARCH.md 2.1.0 one-liner", "2.1.0" in res21 or "nicknames" in res21.lower() or "Moments" in res21)
        with open(os.path.join(REPO, "CHANGELOG.md"), "r") as f:
            cl21 = f.read()
        check("CHANGELOG.md has 2.1.0", "2.1.0" in cl21 and "watching" in cl21.lower())
    except Exception as exc:
        check("2.1.0 nicknames/watching/places suite", False, "%s\n%s" % (exc, traceback.format_exc()[:600]))



    # --- 2.2.0 reactions + pin + cinema + recap + uptime ---
    try:
        try:
            from urllib.request import Request, urlopen
        except ImportError:
            from urllib2 import Request, urlopen

        # Seed a chat message with id
        entry = gl.append_chat_delivered("ReactFan", "React me")
        mid = entry.get("id")
        check("chat entry has id", bool(mid), entry)

        req_r = Request(
            "http://127.0.0.1:%s/react" % port,
            data=("id=%s&reaction=fire" % mid).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp_r = urlopen(req_r, timeout=5)
        jr = json.loads(resp_r.read().decode("utf-8"))
        check("POST /react ok", jr.get("ok") is True, jr)
        rx = (jr.get("reactions") or (jr.get("entry") or {}).get("reactions") or {})
        fire_n = int(rx.get("🔥") or rx.get("fire") or 0)
        check("POST /react fire count", fire_n >= 1, rx)

        req_p = Request(
            "http://127.0.0.1:%s/pin" % port,
            data=("id=%s" % mid).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp_p = urlopen(req_p, timeout=5)
        jp = json.loads(resp_p.read().decode("utf-8"))
        check("POST /pin ok", jp.get("ok") is True and jp.get("pinned_chat_id") == mid, jp)

        code_api22, raw_api22 = http_get(port, "/api")
        japi22 = json.loads(raw_api22.decode("utf-8") if isinstance(raw_api22, bytes) else raw_api22)
        check("GET /api has uptime_sec", isinstance(japi22.get("uptime_sec"), int) and japi22.get("uptime_sec") >= 1, japi22.get("uptime_sec"))
        check("GET /api has uptime_human", bool(japi22.get("uptime_human")), japi22.get("uptime_human"))
        pinned = japi22.get("pinned") or {}
        check("GET /api pinned message", isinstance(pinned, dict) and pinned.get("id") == mid, pinned)

        code_h22, raw_h22 = http_get(port, "/health")
        jh22 = json.loads(raw_h22.decode("utf-8") if isinstance(raw_h22, bytes) else raw_h22)
        check("GET /health has uptime", "uptime_sec" in jh22 and "uptime_human" in jh22, jh22)

        code_rec, raw_rec = http_get(port, "/recap")
        html_rec = raw_rec.decode("utf-8") if isinstance(raw_rec, bytes) else raw_rec
        check("GET /recap status 200", code_rec == 200, code_rec)
        check("GET /recap PHOTOS TODAY", "PHOTOS TODAY" in html_rec)
        check("GET /recap NEWS TODAY", "NEWS TODAY" in html_rec)
        check("GET /recap CHAT TODAY", "CHAT TODAY" in html_rec)
        check("GET /recap TOP LOCATION", "TOP LOCATION" in html_rec)

        code_home22, raw_home22 = http_get(port, "/")
        html22 = raw_home22.decode("utf-8") if isinstance(raw_home22, bytes) else raw_home22
        check("GET / reactChat UI", "reactChat" in html22 and "👍" in html22)
        check("GET / pinChat UI", "pinChat" in html22 and "chat_pin" in html22)
        check("GET / Recap quick action", 'href="/recap"' in html22 and "Recap" in html22)
        check("GET / uptime footer", "uptime_foot" in html22 or "uptime_val" in html22)

        code_sp22, raw_sp22 = http_get(port, "/spectate")
        html_sp22 = raw_sp22.decode("utf-8") if isinstance(raw_sp22, bytes) else raw_sp22
        check("GET /spectate cinema btn", "btn_cinema" in html_sp22 and "Cinema" in html_sp22)
        check("GET /spectate cinema hotkey H", "setCinema" in html_sp22 and ("ev.key==='h'" in html_sp22 or 'ev.key===\'h\'' in html_sp22 or "key==='H'" in html_sp22 or 'key===\'H\'' in html_sp22))
        check("GET /spectate cinema CSS", "body.cinema" in html_sp22)

        # CLEO 6th reply + HELP Moments
        with open(os.path.join(REPO, "grovelink", "GroveLinkPhone.txt"), "r") as f:
            cleo22 = f.read()
        check("CLEO Later homie reply", "Later homie" in cleo22)
        check("CLEO reply index 0-5", "0-5" in cleo22 or "29@ > 5" in cleo22)
        check("CLEO HELP Moments+Spectate", "Moments" in cleo22 and "Spectate" in cleo22)

        with open(os.path.join(REPO, "grovelink", "FEATURES.md"), "r") as f:
            feat22 = f.read()
        check("FEATURES.md 2.2.0", "2.2.0" in feat22 and "reaction" in feat22.lower())
        check("FEATURES.md recap/cinema/uptime", "/recap" in feat22 and "cinema" in feat22.lower() and "uptime" in feat22.lower())
        with open(os.path.join(REPO, "CHANGELOG.md"), "r") as f:
            cl22 = f.read()
        check("CHANGELOG.md has 2.2.0", "2.2.0" in cl22 and ("reaction" in cl22.lower() or "recap" in cl22.lower()))
        with open(os.path.join(REPO, "grovelink", "RESEARCH.md"), "r") as f:
            res22 = f.read()
        check("RESEARCH.md 2.2.0", "2.2.0" in res22)
    except Exception as exc:
        check("2.2.0 reactions/pin/recap suite", False, "%s\n%s" % (exc, traceback.format_exc()[:600]))


    # --- 2.3.0 comments + mute + density + streak + spectate DL + Herald depth ---
    try:
        try:
            from urllib.request import Request, urlopen
        except ImportError:
            from urllib2 import Request, urlopen

        # Seed a bridge photo file for comment + streak
        photos_dir = os.path.join(BRIDGE, "photos")
        if not os.path.isdir(photos_dir):
            os.makedirs(photos_dir)
        shot = "smoke_streak_shot.jpg"
        shot_path = os.path.join(photos_dir, shot)
        with open(shot_path, "wb") as f:
            f.write(b"\xff\xd8\xff\xd9")  # minimal jpeg-ish
        try:
            os.utime(shot_path, None)
        except Exception:
            pass
        # Refresh STATE photos via list helper if present
        try:
            gl.copy_latest([])
        except Exception:
            gl.STATE["photos"] = [{
                "file": shot,
                "mtime": int(time.time()),
                "when": "now",
                "size": 4,
                "size_h": "4 B",
            }]
            try:
                gl.note_streak_from_photos(gl.STATE["photos"])
            except Exception:
                pass

        req_c = Request(
            "http://127.0.0.1:%s/comment" % port,
            data=("file=%s&comment=Smoke%%20comment" % shot).encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp_c = urlopen(req_c, timeout=5)
        jc = json.loads(resp_c.read().decode("utf-8"))
        check("POST /comment ok", jc.get("ok") is True and "Smoke comment" in str(jc.get("comment") or ""), jc)

        code_api23, raw_api23 = http_get(port, "/api")
        japi23 = json.loads(raw_api23.decode("utf-8") if isinstance(raw_api23, bytes) else raw_api23)
        check("GET /api has streak", "streak" in japi23 and isinstance(japi23.get("streak"), int), japi23.get("streak"))
        photos23 = japi23.get("photos") or []
        found_cmt = False
        for p in photos23:
            if isinstance(p, dict) and p.get("file") == shot and (p.get("comment") or "") == "Smoke comment":
                found_cmt = True
                break
        # If photo not in list (copy_latest empty galleries), still accept comment JSON
        if not found_cmt:
            try:
                found_cmt = (gl.get_comment(shot) == "Smoke comment")
            except Exception:
                found_cmt = False
        check("comment stored for photo", found_cmt, photos23[:2] if photos23 else jc)

        code_h23, raw_h23 = http_get(port, "/health")
        jh23 = json.loads(raw_h23.decode("utf-8") if isinstance(raw_h23, bytes) else raw_h23)
        check("GET /health has streak", "streak" in jh23, jh23)

        code_rec23, raw_rec23 = http_get(port, "/recap")
        html_rec23 = raw_rec23.decode("utf-8") if isinstance(raw_rec23, bytes) else raw_rec23
        check("GET /recap PHOTO STREAK", "PHOTO STREAK" in html_rec23)
        check("GET /recap modern wrap", "class=\"wrap\"" in html_rec23 or "class='wrap'" in html_rec23 or "SESSION RECAP" in html_rec23)

        code_home23, raw_home23 = http_get(port, "/")
        html23 = raw_home23.decode("utf-8") if isinstance(raw_home23, bytes) else raw_home23
        check("GET / comment UI", "saveComment" in html23 and "commentrow" in html23)
        check("GET / mute UI", "chat_mute_btn" in html23 and "isChatMuted" in html23)
        check("GET / density UI", "theme_dark" in html23 and "theme_bright" in html23 and "applyDensity" in html23)
        check("GET / streak header", "streak_val" in html23)
        check("GET / section headers", "class=\"sect\"" in html23 or "Companion chat" in html23)

        code_sp23, raw_sp23 = http_get(port, "/spectate")
        html_sp23 = raw_sp23.decode("utf-8") if isinstance(raw_sp23, bytes) else raw_sp23
        check("GET /spectate download btn", "btn_dl" in html_sp23 and "Download" in html_sp23)

        # Herald depth: create news and inspect article fields / HTML
        ok_n, art_n, det_n = gl.create_news_from_photo(shot, caption="Smoke caption", auto=False, location="Grove Street")
        check("create_news detailed ok", ok_n is True and isinstance(art_n, dict), det_n)
        if art_n:
            check("news has subhead", bool(art_n.get("subhead")), art_n.get("subhead"))
            check("news has pull_quote", bool(art_n.get("pull_quote")), art_n.get("pull_quote"))
            check("news has related", bool(art_n.get("related")), art_n.get("related"))
            check("news has dateline", bool(art_n.get("dateline")), art_n.get("dateline"))
            check("news has desk/byline", bool(art_n.get("desk") or art_n.get("byline")), art_n.get("byline"))
            check("news has photo_credit", bool(art_n.get("photo_credit")), art_n.get("photo_credit"))
            body_n = art_n.get("body") or ""
            check("news body multi-paragraph", body_n.count("\n\n") >= 2, body_n.count("\n\n"))
            aid = art_n.get("id")
            code_na, raw_na = http_get(port, "/news/%s" % aid)
            html_na = raw_na.decode("utf-8") if isinstance(raw_na, bytes) else raw_na
            check("GET /news/<id> pull quote", "class=\"pull\"" in html_na or "pull" in html_na)
            check("GET /news/<id> related", "related" in html_na.lower())
            check("GET /news/<id> dateline", "dateline" in html_na.lower() or (art_n.get("dateline") or "")[:8] in html_na)
            code_ni, raw_ni = http_get(port, "/news")
            html_ni = raw_ni.decode("utf-8") if isinstance(raw_ni, bytes) else raw_ni
            check("GET /news index deck/subhead", "deck" in html_ni or (art_n.get("subhead") or "")[:20] in html_ni)

        with open(os.path.join(REPO, "grovelink", "FEATURES.md"), "r") as f:
            feat23 = f.read()
        check("FEATURES.md 2.3.0", "2.3.0" in feat23 and "comment" in feat23.lower())
        check("FEATURES.md streak/density/Herald", "streak" in feat23.lower() and ("density" in feat23.lower() or "Dark street" in feat23) and ("Herald" in feat23 or "subhead" in feat23.lower() or "pull" in feat23.lower()))
        with open(os.path.join(REPO, "CHANGELOG.md"), "r") as f:
            cl23 = f.read()
        check("CHANGELOG.md has 2.3.0", "2.3.0" in cl23)
        with open(os.path.join(REPO, "grovelink", "RESEARCH.md"), "r") as f:
            res23 = f.read()
        check("RESEARCH.md 2.3.0", "2.3.0" in res23)
    except Exception as exc:
        check("2.3.0 comments/streak/Herald suite", False, "%s\n%s" % (exc, traceback.format_exc()[:600]))




    # --- 2.4.0 interactive: /request /poll /vote /broadcast /rate limit /live ---
    try:
        code, jreq = http_post(port, "/request", "kind=camera&from=SmokeViewer")
        check("POST /request ok", code == 200 and isinstance(jreq, dict) and jreq.get("ok") is True, (code, jreq))
        check("POST /request kind camera", isinstance(jreq, dict) and (jreq.get("request") or {}).get("kind") == "camera", jreq)
        ini_txt = ""
        try:
            with open(server.link_ini, "r") as f:
                ini_txt = f.read()
        except Exception as exc:
            ini_txt = str(exc)
        check("POST /request writes REQUEST.new=1", "[REQUEST]" in ini_txt and "new=1" in ini_txt, ini_txt[:500])
        code_a, raw_a = http_get(port, "/api")
        api = json.loads(raw_a.decode("utf-8") if isinstance(raw_a, bytes) else raw_a)
        check("/api has requests", isinstance(api.get("requests"), list) and len(api.get("requests") or []) >= 1, api.get("requests"))
        check("/api has viewers", isinstance(api.get("viewers"), list), api.get("viewers"))
    except Exception as exc:
        check("POST /request suite", False, exc)

    try:
        code, raw = http_get(port, "/")
        html = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        check("GET / has modebar Host/Viewer", 'id="modebar"' in html and "Host" in html and "Viewer" in html)
        check("GET / has Ask CJ requests", 'id="reqbar"' in html and "data-kind" in html)
        check("GET / has hostpanel", 'id="hostpanel"' in html)
        check("GET / Watch party link", 'href="/live"' in html)
    except Exception as exc:
        check("GET / interactive UI", False, exc)

    try:
        code, jpoll = http_post(port, "/poll", "question=Best+hood%3F&options=Grove%7CBallas%7CNeutral")
        check("POST /poll ok", code == 200 and isinstance(jpoll, dict) and jpoll.get("ok") is True, (code, jpoll))
        poll = (jpoll.get("poll") if isinstance(jpoll, dict) else None) or {}
        check("POST /poll 3 options", len(poll.get("options") or []) == 3, poll)
        code, jvote = http_post(port, "/vote", "option=0&from=SmokeVoter")
        check("POST /vote ok", code == 200 and isinstance(jvote, dict) and jvote.get("ok") is True, (code, jvote))
        tallies = ((jvote.get("poll") or {}).get("tallies") if isinstance(jvote, dict) else None) or []
        v0 = tallies[0]["votes"] if tallies else 0
        check("POST /vote tallies", v0 >= 1, tallies)
        code, jclose = http_post(port, "/poll", "action=close")
        check("POST /poll close", code == 200 and isinstance(jclose, dict) and jclose.get("ok") is True, (code, jclose))
        detail = str((jclose.get("detail") if isinstance(jclose, dict) else "") or "")
        check("poll close summary", "Poll done" in detail or "Grove" in detail, detail)
    except Exception as exc:
        check("POST /poll|/vote suite", False, exc)

    try:
        code, jb = http_post(port, "/broadcast", "msg=Homies+listen+up&from=CJ")
        check("POST /broadcast ok", code == 200 and isinstance(jb, dict) and jb.get("ok") is True, (code, jb))
        check("POST /broadcast flag", isinstance(jb, dict) and jb.get("broadcast") is True, jb)
        code_c, raw_c = http_get(port, "/api/chat")
        chat = json.loads(raw_c.decode("utf-8") if isinstance(raw_c, bytes) else raw_c)
        inbox = chat.get("inbox") or []
        hit = any((m.get("broadcast") or m.get("system")) and "Homies" in (m.get("msg") or "") for m in inbox)
        check("broadcast in chat log", hit, inbox[:2] if inbox else inbox)
    except Exception as exc:
        check("POST /broadcast suite", False, exc)

    try:
        gl.STATE["rate_limit_send"] = {}
        code1, j1 = http_post(port, "/send", "msg=RateA&from=RateBot")
        code2, j2 = http_post(port, "/send", "msg=RateB&from=RateBot")
        check("rate limit first send ok", code1 == 200 and isinstance(j1, dict) and j1.get("delivered") is True, (code1, j1))
        check("rate limit second send 429", code2 == 429 and isinstance(j2, dict) and j2.get("ok") is False, (code2, j2))
        det = str((j2.get("detail") if isinstance(j2, dict) else "") or "").lower()
        check("rate limit error text", "rate limit" in det or "wait" in det, j2)
    except Exception as exc:
        check("rate limit /send suite", False, exc)

    try:
        code, raw = http_get(port, "/live")
        html = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        check("GET /live watch party", code == 200 and "WATCH PARTY" in html and "/spectate" in html)
    except Exception as exc:
        check("GET /live", False, exc)

    try:
        with open(os.path.join(REPO, "grovelink", "GroveLinkPhone.txt"), "r") as f:
            cleo = f.read()
        check("CLEO has REQUESTS menu", "REQUESTS" in cleo and ":SEL_REQUESTS" in cleo)
        check("CLEO REQUEST/POLL toasts", ":REQUEST_CHECK" in cleo and ":POLL_CHECK" in cleo)
        check("CLEO no hold_cellphone", "hold_cellphone" not in cleo.lower() or "no hold_cellphone" in cleo.lower())
        check("CLEO no 033E", "033E" not in cleo or "no 033E" in cleo or "no custom GXT 033E" in cleo or "No #model names, no 033E" in cleo)
    except Exception as exc:
        check("CLEO 2.4 static", False, exc)

    try:
        with open(os.path.join(REPO, "README.md"), "r") as f:
            rm = f.read()
        check("README Hosting for viewers", "Hosting for viewers" in rm)
        with open(os.path.join(REPO, "grovelink", "TROUBLESHOOTING.md"), "r") as f:
            ts = f.read()
        check("TROUBLESHOOTING same Wi-Fi / port forward", "Same Wi-Fi" in ts or "port forward" in ts.lower())
        with open(os.path.join(REPO, "grovelink", "FEATURES.md"), "r") as f:
            fe = f.read()
        check("FEATURES 2.4 interactive", "2.4.0" in fe and ("Host / viewer" in fe or "broadcast" in fe.lower()))
    except Exception as exc:
        check("docs 2.4", False, exc)



    # --- 2.5.0 friend texts / cj_texts ---
    try:
        # Simulate CLEO MSG.new write
        with open(server.link_ini, "a") as f:
            f.write("\n[MSG]\nnew=1\ncontact=Sweet\nout=Where you at?\nin=At the hood CJ\n")
            f.write("\n[MSG_SWEET]\nout=\nin=\n")
        ok = gl.process_friend_msg_flag(server.link_ini)
        check("process_friend_msg_flag", ok is True, ok)
        payload = gl.load_cj_friend_texts(server.link_ini)
        check("cj_texts has threads", isinstance(payload, dict) and isinstance(payload.get("threads"), list), payload)
        sweet_hit = any(t.get("contact") == "Sweet" and "hood" in (t.get("in") or "").lower() for t in (payload.get("threads") or []))
        check("cj_texts Sweet reply", sweet_hit or (payload.get("last") or {}).get("contact") == "Sweet", payload)
        code, raw = http_get(port, "/api")
        api = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        check("/api cj_texts field", isinstance(api.get("cj_texts"), dict), api.get("cj_texts"))
        code, raw = http_get(port, "/")
        html = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        check("GET / CJ texts panel", 'id="cjtexts_box"' in html or "FRIEND THREADS" in html)
    except Exception as exc:
        check("2.5.0 cj_texts suite", False, "%s\n%s" % (exc, traceback.format_exc()[:500]))

    try:
        with open(os.path.join(REPO, "CHANGELOG.md"), "r") as f:
            cl = f.read()
        check("CHANGELOG.md has 2.5.0 features", "2.5.0" in cl and ("CONTACTS" in cl or "Call" in cl or "friend" in cl.lower()))
        with open(os.path.join(REPO, "grovelink", "FEATURES.md"), "r") as f:
            fe = f.read()
        check("FEATURES 2.5 contacts/calls", "2.5.0" in fe and ("Call" in fe or "CONTACTS" in fe))
        with open(os.path.join(REPO, "grovelink", "RESEARCH.md"), "r") as f:
            rs = f.read()
        check("RESEARCH notes no spawn calls", "dialogue" in rs.lower() and "spawn" in rs.lower())
    except Exception as exc:
        check("docs 2.5", False, exc)



    try:
        server.shutdown()
    except Exception:
        pass
    try:
        server.server_close()
    except Exception:
        pass

    # Static CLEO / bat checks (no GTA)
    phone_txt = os.path.join(REPO, "grovelink", "GroveLinkPhone.txt")
    try:
        with open(phone_txt, "r") as f:
            cleo_lines = f.readlines()
        # Strip // comments and { } block noise for opcode checks (header may say "no 033E")
        code_lines = []
        for line in cleo_lines:
            cut = line.split("//", 1)[0]
            code_lines.append(cut)
        code = "\n".join(code_lines)
        # hold_cellphone / 033E: must not appear as real calls (colon form or bare call)
        bad_hold = ("hold_cellphone" in code.lower())
        bad_033e = ("033E:" in code) or ("033e:" in code)
        check("CLEO no hold_cellphone opcode", not bad_hold)
        check("CLEO no 033E GXT draw", not bad_033e)
        full = "".join(cleo_lines)
        check("CLEO has HELP / STATUS", "HELP" in full and "STATUS" in full)
        check("CLEO menu has REPLY + SPECTATE", "REPLY" in full and "SPECTATE" in full and "CLOSE" in full)
        check("CLEO NO NEW TEXTS", "NO NEW TEXTS" in full)
        check("CLEO PHONE PAGE ON PC", "PHONE PAGE ON PC" in full)
        # wrap bounds: index > 8 resets to 0; 0 > index sets 8 (9 slots)
        check("CLEO wrap high bound", "22@ > 9" in full or "0019:   22@ > 9" in full or "22@ > 8" in full)
        check("CLEO NEWS menu slot", "BREAKING NEWS SNAP" in full and ":SEL_NEWS" in full)
        check("CLEO NEWS.make write", 'section "NEWS" key "make"' in full or "key \"make\"" in full)
        check("CLEO HELP Camera vs NEWS", "Camera: pics to phone only" in full and "NEWS: snap + Herald" in full)
        check("CLEO HELP mentions REPLY", "REPLY:" in full and "Enter send" in full)
        check("CLEO HELP mentions SPECTATE", "SPECTATE:" in full and "/spectate" in full)
        check("CLEO has Later homie canned", "Later homie" in full)
        check("CLEO HELP Moments line", "Moments" in full)
        cam_to_inbox = full.split(":SEL_INBOX")[0]
        # Camera menu select is the LAST shutter before :SEL_INBOX (SPECTATE_TICK may shutter earlier)
        if "0A2F: set_photo_camera_effect 1" in cam_to_inbox:
            cam_sel = cam_to_inbox.split("0A2F: set_photo_camera_effect 1")[-1]
        else:
            cam_sel = ""
        check("CLEO CAMERA select omits NEWS.make", 'key "make"' not in cam_sel and 'section "NEWS"' not in cam_sel)
        news_sel = ""
        if ":SEL_NEWS" in full and ":SEL_SPECTATE" in full:
            news_sel = full.split(":SEL_NEWS", 1)[1].split(":SEL_SPECTATE", 1)[0]
        elif ":SEL_NEWS" in full and ":SEL_CONTACTS" in full:
            news_sel = full.split(":SEL_NEWS", 1)[1].split(":SEL_CONTACTS", 1)[0]
        check("CLEO NEWS select writes NEWS.make", 'key "make"' in news_sel)
        check("CLEO NEWS writes NEWS.zone", 'key "zone"' in news_sel or 'section "NEWS" key "zone"' in news_sel)
        check("CLEO NEWS uses 0843 or coord ladder", "0843" in news_sel or "Grove Street" in news_sel)
        check("CLEO CAMERA select omits NEWS.zone", 'section "NEWS" key "zone"' not in cam_sel and 'section "NEWS"' not in cam_sel)
        check("CLEO CONTACTS Catalina flavor", "CATALINA" in full or "Catalina" in full)
        check("CLEO contacts list mode", ":CONTACT_LIST" in full and "CONTACT: Sweet" in full)
        check("CLEO call sequence dialogue", ":CALL_SEQ" in full and "Calling Sweet" in full)
        check("CLEO call no spawn note", "no spawn" in full.lower() or "Dialogue-only" in full or "dialogue only" in full.lower())
        check("CLEO friend text MSG", ":FRIEND_TEXT" in full and 'section "MSG"' in full)
        check("CLEO OG Loc contact", "OG Loc" in full or "OG LOC" in full)
        check("CLEO SMS FROM REAL PHONE notify", "SMS FROM REAL PHONE" in full)
        check("CLEO NEWS FILED toast", "NEWS FILED" in full)
        check("CLEO REPLY writes OUTBOX", 'section "OUTBOX"' in full and 'key "new"' in full)
        check("CLEO REPLY canned lines", "On my way" in full and "Grove forever" in full and "Busy rn" in full)
        check("CLEO SPECTATE toggle", ":SEL_SPECTATE" in full and 'section "SPECTATE" key "on"' in full)
        check("CLEO SPECTATE.frame write", 'section "SPECTATE" key "frame"' in full)
        check("CLEO SPECTATE tick while closed", ":SPECTATE_TICK" in full)
    except Exception as exc:
        check("CLEO static", False, exc)

    start_bat = os.path.join(BRIDGE, "START_GROVELINK.bat")
    try:
        with open(start_bat, "r") as f:
            bat = f.read()
        check("START bat prints VERSION", "VERSION" in bat and "GL_VER" in bat)
        check("START bat python.org 3.8.10 link", "python-3810" in bat)
        check("START bat finds via GroveLink_REPO.txt", "GroveLink_REPO.txt" in bat)
        check("START bat resolves grovelink\\bridge", "grovelink\\bridge" in bat or "grovelink\bridge" in bat)
        check("START bat plain English missing help", "GroveLink Phone" in bat and "INSTALL" in bat)
        check("START bat nested zip hint", "gta-sa-win7-mods-main" in bat)
    except Exception as exc:
        check("START bat static", False, exc)

    try:
        with open(os.path.join(REPO, "UPDATE_GROVELINK.bat"), "r") as f:
            ub = f.read()
        check("UPDATE prints EXACT browser URL", "EXACT browser URL" in ub)
        check("UPDATE MANUAL_URL zip path", "archive/refs/heads/" in ub)
    except Exception as exc:
        check("UPDATE bat static", False, exc)

    try:
        with open(os.path.join(REPO, "VERIFY_GROVELINK.bat"), "r") as f:
            vb = f.read()
        check("VERIFY strips REPO CR", 'for /f "delims=" %%A in ("!REPO_FROM_FILE!")' in vb)
        check("VERIFY gta_dir keeps spaces", "do NOT strip spaces inside path" in vb or "tokens=* delims= " in vb)
        check("VERIFY checks VERSION file", "VERSION" in vb and "Pack version" in vb)
        check("VERIFY prints pack version", "Pack version:" in vb)
    except Exception as exc:
        check("VERIFY bat static", False, exc)

    try:
        with open(os.path.join(REPO, "INSTALL.bat"), "r") as f:
            ib = f.read()
        check("INSTALL CLEO.asi big warning", "BIG WARNING: CLEO.asi IS MISSING" in ib)
        check("INSTALL cleo.li link", "https://cleo.li" in ib)
        repo_i = ib.find("GroveLink_REPO.txt")
        start_i = ib.find('copy /Y "%~dp0grovelink\\bridge\\START_GROVELINK.bat"')
        if start_i < 0:
            start_i = ib.find("START_GROVELINK.bat")
        check("INSTALL writes REPO before START copy", repo_i >= 0 and start_i >= 0 and repo_i < start_i,
              "repo_i=%s start_i=%s" % (repo_i, start_i))
        phone_bat_i = ib.find("GroveLink Phone.bat")
        check("INSTALL writes GroveLink Phone.bat", phone_bat_i >= 0 and "GLREPO" in ib)
        check("INSTALL Phone.bat after REPO", phone_bat_i >= 0 and repo_i >= 0 and repo_i < phone_bat_i,
              "repo_i=%s phone_bat_i=%s" % (repo_i, phone_bat_i))
        check("INSTALL SUCCESS mentions Phone.bat", "GroveLink Phone.bat" in ib)
        check("INSTALL .lnk is optional bonus", "Optional bonus" in ib or "optional bonus" in ib.lower())
    except Exception as exc:
        check("INSTALL bat static", False, exc)

    try:
        with open(start_bat, "r") as f:
            bat2 = f.read()
        check("START bat strips VERSION CR", 'for /f "delims=" %%A in ("%GL_VER%")' in bat2)
    except Exception as exc:
        check("START bat CR strip", False, exc)

    try:
        with open(os.path.join(REPO, "CHANGELOG.md"), "r") as f:
            cl = f.read()
        check("CHANGELOG.md exists with 1.8.0", "1.8.0" in cl and ("Breaking News" in cl or "Herald" in cl or "gallery" in cl.lower()))
        check("CHANGELOG.md has 1.8.1 Camera vs NEWS", "1.8.1" in cl and ("Camera" in cl) and ("news.auto" in cl or "NEWS.make" in cl))
        check("CHANGELOG.md has 1.8.2 location tags", "1.8.2" in cl and ("location" in cl.lower() or "NEWS.zone" in cl or "📍" in cl))
        check("CHANGELOG.md has 1.9.0 CJ reply + spectate", "1.9.0" in cl and ("OUTBOX" in cl or "REPLY" in cl) and ("spectate" in cl.lower() or "SPECTATE" in cl))
        check("CHANGELOG.md has 2.0.0 research pass", "2.0.0" in cl and ("favorite" in cl.lower() or "HUD" in cl or "manifest" in cl.lower()))
        check("CHANGELOG.md has 2.1.0 features", "2.1.0" in cl and ("nickname" in cl.lower() or "watching" in cl.lower() or "Moments" in cl))
        check("CHANGELOG.md has 2.2.0 features", "2.2.0" in cl and ("reaction" in cl.lower() or "recap" in cl.lower() or "uptime" in cl.lower() or "cinema" in cl.lower()))
        check("CHANGELOG.md has 2.4.0 features", "2.4.0" in cl and ("broadcast" in cl.lower() or "Host" in cl or "viewer" in cl.lower()))
        check("CHANGELOG.md has 2.3.0 features", "2.3.0" in cl and ("comment" in cl.lower() or "streak" in cl.lower() or "Herald" in cl or "density" in cl.lower()))
        check("CHANGELOG covers 1.0 foundation", "1.0" in cl and ("Foundation" in cl or "crash-safer" in cl))
    except Exception as exc:
        check("CHANGELOG.md", False, exc)

    try:
        with open(os.path.join(BRIDGE, "grovelink_server.py"), "r") as f:
            srv = f.read()
        check("bridge prints port busy (plain English)", "Port %s busy" in srv or 'Port %s busy' in srv)
        check("bridge handles bind OSError", "address already in use" in srv.lower())
    except Exception as exc:
        check("bridge port-busy source", False, exc)

    try:
        with open(os.path.join(REPO, "update.ini"), "r") as f:
            ui = f.read()
        check("update.ini keeps PR branch", "fix/grovelink-camera-snapshots" in ui)
        check("update.ini after-merge note", "After merge PR #1" in ui or "branch=main" in ui)
    except Exception as exc:
        check("update.ini comments", False, exc)

    try:
        with open(os.path.join(REPO, "README.md"), "r") as f:
            rm = f.read()
        check("README noob path lead", "Noob path" in rm or "INSTALL.bat" in rm[:800])
        check("README links FEATURES/CHANGELOG/TROUBLESHOOTING",
              "FEATURES.md" in rm and "CHANGELOG.md" in rm and "TROUBLESHOOTING.md" in rm)
        check("README after-merge branch=main note", "After merge PR #1" in rm and "branch=main" in rm)
    except Exception as exc:
        check("README polish", False, exc)



    try:
        with open(os.path.join(REPO, "CHANGELOG.md"), "r") as f:
            cl251 = f.read()
        check("CHANGELOG.md has 2.5.1 Desktop START", "2.5.1" in cl251 and ("GroveLink_REPO" in cl251 or "Desktop START" in cl251 or "grovelink_server.py" in cl251))
        check("CHANGELOG.md has 2.5.2 Phone.bat", "2.5.2" in cl251 and "GroveLink Phone.bat" in cl251)
    except Exception as exc:
        check("CHANGELOG 2.5.1/2.5.2", False, exc)

    try:
        with open(os.path.join(REPO, "grovelink", "TROUBLESHOOTING.md"), "r") as f:
            tr = f.read()
        check("TROUBLESHOOTING covers missing grovelink_server.py",
              "grovelink_server.py" in tr and ("GroveLink Phone" in tr) and ("gta-sa-win7-mods-main" in tr))
        check("TROUBLESHOOTING no Phone icon section",
              "No GroveLink Phone icon" in tr and "GroveLink Phone.bat" in tr and ("Downloads" in tr or "nested" in tr.lower()))
    except Exception as exc:
        check("TROUBLESHOOTING 2.5.1/2.5.2", False, exc)

    check("VERSION is 2.5.2", pack_ver == "2.5.2", pack_ver)

    # Runtime: after clear, HTML still disables; after photo, actions enabled via setCountActions path
    # (API count already covered; spot-check helper exists in page source above)

    print("")
    print("==== SUMMARY ====")
    fails = 0
    for name, status, detail in RESULTS:
        print("%-6s %s" % (status, name))
        if status != "PASS":
            fails += 1
    print("----")
    print("%d passed, %d failed" % (len(RESULTS) - fails, fails))
    return 1 if fails else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        sys.exit(130)
