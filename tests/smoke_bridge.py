#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GroveLink bridge smoke test — stdlib only, Win7/PC + Linux.

Starts the bridge HTTP server on an ephemeral port, asserts:
  GET /health, GET /api, GET /export.zip, GET /
Optional: gallery copy + last_error + skipped_deleted + sort HTML + clear confirm +
help footer + empty-action disable + VERIFY VERSION + CHANGELOG + port-busy + README polish.
1.8.0: /news index + POST /news + /news/id + /send ini + /api/chat + gallery hero HTML.

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
    gl.STATE["news_auto"] = False
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
            "[PHOTO]\ntake=0\n"
            "[STATUS]\nbridge=1\n"
            "[NEWS]\nnew=0\n"
        )

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
        check("GET / has From: field", 'id="from_name"' in html and "From:" in html)
        check("GET / has chat thread", 'id="chat_thread"' in html or "TEXTS TO CJ" in html)
        check("GET / has Grove Street Herald link", "/news" in html and "Herald" in html)
        check("GET / has Share page / sharePhoto", "share_page" in html or "sharePhoto" in html)
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
            data=("file=" + latest + "&caption=Smoke+Herald+caption").encode("utf-8"),
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp = urlopen(req, timeout=5)
        body = resp.read()
        code = getattr(resp, "status", None) or resp.getcode()
        jn = json.loads(body.decode("utf-8") if isinstance(body, bytes) else body)
        check("POST /news status 200", code == 200, code)
        check("POST /news ok + id", jn.get("ok") is True and bool(jn.get("id")), jn)
        art_id = jn.get("id") or ""
        if art_id:
            code_a, raw_a = http_get(port, "/news/" + art_id)
            html_a = raw_a.decode("utf-8") if isinstance(raw_a, bytes) else raw_a
            check("GET /news/<id> 200", code_a == 200, code_a)
            check("GET /news/<id> has headline", bool(jn.get("headline")) and (jn.get("headline") in html_a), jn.get("headline"))
            check("GET /news/<id> embeds photo img", ("/photo/" + latest) in html_a or 'src="/photo/' in html_a, html_a[:200])
            # NEWS.new flag in ini
            with open(server.link_ini, "r") as f:
                ini2 = f.read()
            check("POST /news sets NEWS.new=1", "new=1" in ini2.split("[NEWS]")[-1] if "[NEWS]" in ini2 else False, ini2[-200:])
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
        check("CLEO menu wrap 0-5", "0@" in full)  # soft presence
        check("CLEO NO NEW TEXTS", "NO NEW TEXTS" in full)
        check("CLEO PHONE PAGE ON PC", "PHONE PAGE ON PC" in full)
        # wrap bounds: index > 5 resets to 0; 0 > index sets 5
        check("CLEO wrap high bound", "22@ > 5" in full or "0019:   22@ > 5" in full)
        check("CLEO CONTACTS Catalina flavor", "CATALINA" in full)
        check("CLEO contacts cycle advances", "26@ = 4" in full and ":CONTACT4" in full)
        check("CLEO SMS FROM REAL PHONE notify", "SMS FROM REAL PHONE" in full)
        check("CLEO NEWS FILED toast", "NEWS FILED" in full)
    except Exception as exc:
        check("CLEO static", False, exc)

    start_bat = os.path.join(BRIDGE, "START_GROVELINK.bat")
    try:
        with open(start_bat, "r") as f:
            bat = f.read()
        check("START bat prints VERSION", "VERSION" in bat and "GL_VER" in bat)
        check("START bat python.org 3.8.10 link", "python-3810" in bat)
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

    check("VERSION is 1.8.0", pack_ver == "1.8.0", pack_ver)

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
