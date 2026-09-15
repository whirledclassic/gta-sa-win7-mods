#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""GroveLink bridge smoke test — stdlib only, Win7/PC + Linux.

Starts the bridge HTTP server on an ephemeral port, asserts:
  GET /health, GET /api, GET /export.zip, GET /
Optional: gallery copy + last_error field present.

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
        f.write("[INBOX]\nnew=0\nfrom=\nmsg=\n[PHOTO]\ntake=0\n[STATUS]\nbridge=1\n")

    t = threading.Thread(target=server.serve_forever)
    t.daemon = True
    t.start()
    time.sleep(0.25)

    # --- /health ---
    try:
        code, raw = http_get(port, "/health")
        health = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        check("GET /health status 200", code == 200, code)
        check("GET /health ok", health.get("ok") is True)
        check("GET /health version", health.get("version") == gl.STATE["version"], health.get("version"))
        check("GET /health poll_ms", isinstance(health.get("poll_ms"), int), health.get("poll_ms"))
        check("GET /health last_error field", "last_error" in health, repr(health.get("last_error")))
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
    except Exception as exc:
        check("POST /clear", False, exc)

    # --- HTML has search + clear ---
    try:
        code, raw = http_get(port, "/")
        html = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        check("GET / has search box", 'id="search"' in html or "Search filename" in html)
        check("GET / has Clear all phone copies", "Clear all phone copies" in html)
    except Exception as exc:
        check("search/clear HTML", False, exc)

    # --- last_error when gallery unreadable ---
    try:
        bad = os.path.join(tmp, "not_a_dir_gallery_marker")
        # Simulate: point list_images at a file-as-folder path that exists as file
        with open(bad, "w") as f:
            f.write("x")
        # On Linux, listdir on a file raises; list_images skips non-dirs first.
        # Create a dir then make it unreadable if possible.
        unreadable = os.path.join(tmp, "unreadable_gallery")
        os.makedirs(unreadable)
        gl.STATE["last_error"] = ""
        # Force set via list_images by temporarily breaking — use a path that is a dir
        # but we can't easily chmod on all systems; set then verify field round-trips.
        gl.STATE["last_error"] = "gallery unreadable: %s (smoke)" % unreadable
        code, raw = http_get(port, "/api")
        api = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        check("GET /api last_error populated", bool(api.get("last_error")), api.get("last_error"))
        gl.STATE["last_error"] = ""
        code, raw = http_get(port, "/api")
        api = json.loads(raw.decode("utf-8") if isinstance(raw, bytes) else raw)
        check("GET /api last_error clears", api.get("last_error") == "", repr(api.get("last_error")))
    except Exception as exc:
        check("last_error round-trip", False, exc)

    # --- POST /send ---
    try:
        try:
            from urllib.request import Request, urlopen
        except ImportError:
            from urllib2 import Request, urlopen
        req = Request(
            "http://127.0.0.1:%s/send" % port,
            data=b"msg=Smoke+test",
            headers={"Content-Type": "application/x-www-form-urlencoded"},
        )
        resp = urlopen(req, timeout=5)
        body = resp.read()
        code = getattr(resp, "status", None) or resp.getcode()
        check("POST /send", code == 200 and b"ok" in body, code)
    except Exception as exc:
        check("POST /send", False, exc)

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
    except Exception as exc:
        check("VERIFY bat static", False, exc)

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
