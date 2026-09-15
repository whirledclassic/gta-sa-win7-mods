# GroveLink bridge — Windows 7, Python 2.7 or 3.4-3.8, stdlib only
from __future__ import print_function

import json
import os
import shutil
import socket
import sys
import threading
import time
import zipfile

try:
    from io import BytesIO
except ImportError:
    from StringIO import StringIO as BytesIO

try:
    from configparser import ConfigParser
except ImportError:
    from ConfigParser import SafeConfigParser as ConfigParser

try:
    from http.server import BaseHTTPRequestHandler, HTTPServer
except ImportError:
    from BaseHTTPServer import BaseHTTPRequestHandler, HTTPServer

try:
    from urllib.parse import parse_qs, unquote
except ImportError:
    from urlparse import parse_qs
    from urllib import unquote

try:
    import webbrowser
except ImportError:
    webbrowser = None

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(HERE, "config.ini")
WEB_PHOTOS = os.path.join(HERE, "photos")
OPEN_PHONE_TXT = os.path.join(HERE, "OPEN_ON_PHONE.txt")
DELETED_PATH = os.path.join(HERE, "photos_deleted.txt")
# Repo-root VERSION (bridge is grovelink/bridge → ../..)
VERSION_PATH = os.path.normpath(os.path.join(HERE, "..", "..", "VERSION"))
DELETED = set()  # basenames in bridge/photos the user removed from the phone UI


def read_pack_version():
    """Plain-text semver from repo-root VERSION (best-effort)."""
    try:
        if os.path.isfile(VERSION_PATH):
            with open(VERSION_PATH, "r") as f:
                line = f.readline().strip()
                if line:
                    return line
    except Exception:
        pass
    return "unknown"


def load_deleted():
    DELETED.clear()
    if not os.path.isfile(DELETED_PATH):
        return
    try:
        with open(DELETED_PATH, "r") as f:
            for line in f:
                name = os.path.basename(line.strip())
                if name:
                    DELETED.add(name)
    except Exception:
        pass


def save_deleted():
    try:
        _mkdir(os.path.dirname(DELETED_PATH) or HERE)
        with open(DELETED_PATH, "w") as f:
            for name in sorted(DELETED):
                f.write(name + "\n")
    except Exception as exc:
        print("Could not save deleted list:", exc)



# Shared runtime state (watcher + HTTP handler)
STATE = {
    "photos": [],
    "inbox": [],
    "sent": 0,
    "galleries": [],
    "ip": "127.0.0.1",
    "port": 8088,
    "gta_dir": "",
    "bridge_ok": True,
    "last_refresh": 0,
    "last_refresh_human": "",
    "shutter_burst_until": 0,
    "max_photos": 40,
    "poll_ms": 2000,
    "phone_page_logged": False,
    "version": "unknown",
    "last_error": "",
}


def read_cfg():
    cfg = ConfigParser()
    if os.path.isfile(CFG_PATH):
        try:
            cfg.read(CFG_PATH)
        except Exception:
            pass
    return cfg


def cfg_get(cfg, section, key, default=""):
    try:
        if cfg.has_option(section, key):
            return cfg.get(section, key).strip()
    except Exception:
        pass
    return default


def cfg_flag(cfg, section, key, default=True):
    """Truthy config flag: 1/true/yes/on. Default used when missing."""
    raw = cfg_get(cfg, section, key, "")
    if raw == "":
        return default
    return raw.lower() in ("1", "true", "yes", "on")


def detect_gta_dir(cfg):
    hinted = cfg_get(cfg, "paths", "gta_dir")
    candidates = [
        hinted,
        r"C:\Program Files (x86)\Rockstar Games\GTA San Andreas",
        r"C:\Program Files\Rockstar Games\GTA San Andreas",
        r"C:\Games\GTA San Andreas",
        r"D:\Games\GTA San Andreas",
        r"E:\Games\GTA San Andreas",
        r"E:\GTA San Andreas",
        r"D:\GTA San Andreas",
        r"C:\GTA San Andreas",
    ]
    for path in candidates:
        if not path:
            continue
        if os.path.isfile(os.path.join(path, "gta_sa.exe")):
            return path
        if os.path.isdir(os.path.join(path, "CLEO")):
            return path
    return hinted


def detect_gallery(cfg, gta_dir):
    home = os.path.expanduser("~")
    user = os.environ.get("USERPROFILE", home)
    public = os.environ.get("PUBLIC", r"C:\Users\Public")
    candidates = [
        cfg_get(cfg, "paths", "gallery_dir"),
        cfg_get(cfg, "paths", "gallery_dir_alt"),
        os.path.join(user, "Documents", "GTA San Andreas User Files", "Gallery"),
        os.path.join(user, "My Documents", "GTA San Andreas User Files", "Gallery"),
        os.path.join(home, "Documents", "GTA San Andreas User Files", "Gallery"),
        os.path.join(public, "Documents", "GTA San Andreas User Files", "Gallery"),
        os.path.join(gta_dir or "", "Gallery"),
        os.path.join(gta_dir or "", "User Files", "Gallery"),
    ]
    found = []
    seen = set()
    for path in candidates:
        if path and os.path.isdir(path) and path not in seen:
            seen.add(path)
            found.append(path)
    return found


def link_ini_path(gta_dir):
    if not gta_dir:
        return os.path.join(HERE, "link.ini")
    return os.path.join(gta_dir, "CLEO", "GroveLink", "link.ini")


def _is_windows():
    return os.name == "nt"


def _looks_like_win_abs(path):
    """True for paths like C:\\... — skip creating those on non-Windows."""
    if not path:
        return False
    # Drive-letter absolute (C:\...) or UNC (\\server\...)
    if len(path) >= 2 and path[1] == ":" and path[0].isalpha():
        return True
    if path.startswith("\\\\") or path.startswith("//"):
        return True
    return False


def _mkdir(path):
    if not path or os.path.isdir(path):
        return
    # Do not mkdir Windows-style absolute paths when running on Linux/mac
    if (not _is_windows()) and _looks_like_win_abs(path):
        return
    try:
        os.makedirs(path)
    except Exception:
        pass


def ensure_gallery_dirs(cfg, gta_dir):
    """Create expected Gallery folders so detect_gallery can find them later."""
    home = os.path.expanduser("~")
    user = os.environ.get("USERPROFILE", home)
    # Only use Public default on real Windows; elsewhere omit to avoid C:\\ litter
    if _is_windows():
        public = os.environ.get("PUBLIC", r"C:\Users\Public")
    else:
        public = os.environ.get("PUBLIC", "")
    candidates = [
        cfg_get(cfg, "paths", "gallery_dir"),
        cfg_get(cfg, "paths", "gallery_dir_alt"),
        os.path.join(user, "Documents", "GTA San Andreas User Files", "Gallery"),
        os.path.join(user, "My Documents", "GTA San Andreas User Files", "Gallery"),
        os.path.join(home, "Documents", "GTA San Andreas User Files", "Gallery"),
        os.path.join(public, "Documents", "GTA San Andreas User Files", "Gallery") if public else "",
        os.path.join(gta_dir or "", "Gallery") if gta_dir else "",
        os.path.join(gta_dir or "", "User Files", "Gallery") if gta_dir else "",
    ]
    for path in candidates:
        if not path:
            continue
        if (not _is_windows()) and _looks_like_win_abs(path):
            continue
        parent = os.path.dirname(path)
        if parent:
            _mkdir(parent)
        _mkdir(path)


def ensure_dirs(cfg, gta_dir):
    _mkdir(WEB_PHOTOS)
    ensure_gallery_dirs(cfg, gta_dir)
    if not gta_dir:
        return
    folder = os.path.join(gta_dir, "CLEO", "GroveLink")
    _mkdir(folder)
    ini = link_ini_path(gta_dir)
    if not os.path.isfile(ini):
        try:
            with open(ini, "w") as f:
                f.write(
                    "[PHOTO]\ntake=0\ncount=0\n\n"
                    "[INBOX]\nnew=0\nfrom=REAL PHONE\nmsg=\n\n"
                    "[STATUS]\nbridge=1\nip=0.0.0.0\n"
                )
        except Exception:
            pass


def human_time(mtime):
    """Local human-readable stamp; works on Py2.7 and 3.x."""
    try:
        return time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(mtime))
    except Exception:
        return str(int(mtime))


def human_size(nbytes):
    """Short file size for phone meta line."""
    try:
        n = int(nbytes)
    except Exception:
        return "?"
    if n < 1024:
        return "%d B" % n
    if n < 1024 * 1024:
        return "%.1f KB" % (n / 1024.0)
    return "%.1f MB" % (n / (1024.0 * 1024.0))


def cfg_int(cfg, section, key, default):
    raw = cfg_get(cfg, section, key, "")
    if raw == "":
        return default
    try:
        return int(raw)
    except Exception:
        return default


def stamp_now():
    now = time.time()
    STATE["last_refresh"] = int(now)
    STATE["last_refresh_human"] = human_time(now)
    return now


def list_images(folders):
    out = []
    seen = set()
    gallery_err = ""
    for folder in folders:
        if not folder or not os.path.isdir(folder):
            continue
        try:
            names = os.listdir(folder)
        except Exception as exc:
            gallery_err = "gallery unreadable: %s (%s)" % (folder, exc)
            continue
        for name in names:
            low = name.lower()
            if not (
                low.endswith(".jpg")
                or low.endswith(".jpeg")
                or low.endswith(".bmp")
                or low.endswith(".png")
            ):
                continue
            full = os.path.join(folder, name)
            if full in seen:
                continue
            seen.add(full)
            try:
                mtime = os.path.getmtime(full)
                size = os.path.getsize(full)
            except Exception:
                continue
            if size < 100:
                continue
            out.append((mtime, full, name))
    out.sort(key=lambda x: x[0], reverse=True)
    # Surface gallery read failures to /api as last_error (cleared when OK)
    if gallery_err:
        STATE["last_error"] = gallery_err
    elif folders:
        prev = STATE.get("last_error") or ""
        if prev.startswith("gallery unreadable"):
            STATE["last_error"] = ""
    return out


def prune_bridge_photos(max_photos):
    """Keep only newest max_photos files under bridge/photos (never Gallery)."""
    try:
        max_photos = int(max_photos)
    except Exception:
        max_photos = 40
    if max_photos < 1:
        max_photos = 1
    if not os.path.isdir(WEB_PHOTOS):
        return
    entries = []
    try:
        names = os.listdir(WEB_PHOTOS)
    except Exception:
        return
    for name in names:
        low = name.lower()
        if not (
            low.endswith(".jpg")
            or low.endswith(".jpeg")
            or low.endswith(".bmp")
            or low.endswith(".png")
        ):
            continue
        full = os.path.join(WEB_PHOTOS, name)
        if not os.path.isfile(full):
            continue
        try:
            mtime = os.path.getmtime(full)
        except Exception:
            continue
        entries.append((mtime, full, name))
    entries.sort(key=lambda x: x[0], reverse=True)
    for _mtime, full, name in entries[max_photos:]:
        try:
            os.remove(full)
            print("Pruned old bridge photo:", name)
        except Exception:
            pass


def copy_latest(folders):
    images = list_images(folders)
    max_photos = int(STATE.get("max_photos") or 40)
    if max_photos < 1:
        max_photos = 1
    copied = []
    for mtime, full, name in images[:max_photos]:
        dest_name = "%d_%s" % (int(mtime), name.replace(" ", "_"))
        if dest_name in DELETED:
            continue
        dest = os.path.join(WEB_PHOTOS, dest_name)
        if not os.path.isfile(dest):
            try:
                shutil.copy2(full, dest)
            except Exception:
                continue
        try:
            size = os.path.getsize(dest)
        except Exception:
            try:
                size = os.path.getsize(full)
            except Exception:
                size = 0
        copied.append({
            "file": dest_name,
            "mtime": int(mtime),
            "when": human_time(mtime),
            "size": int(size),
            "size_h": human_size(size),
        })
    prune_bridge_photos(max_photos)
    # Drop any pruned/deleted from list; re-scan bridge folder for leftovers
    kept = []
    seen = set()
    for item in copied:
        name = item.get("file")
        dest = os.path.join(WEB_PHOTOS, name)
        if name in DELETED or not os.path.isfile(dest):
            continue
        kept.append(item)
        seen.add(name)
    # Also list bridge photos not from gallery copy (manual drops) up to max
    try:
        bridge_names = os.listdir(WEB_PHOTOS)
    except Exception as exc:
        STATE["last_error"] = "bridge photos unreadable: %s" % exc
        bridge_names = []
    try:
        for name in bridge_names:
            if name in seen or name in DELETED:
                continue
            low = name.lower()
            if not (
                low.endswith(".jpg")
                or low.endswith(".jpeg")
                or low.endswith(".bmp")
                or low.endswith(".png")
            ):
                continue
            dest = os.path.join(WEB_PHOTOS, name)
            if not os.path.isfile(dest):
                continue
            try:
                mtime = os.path.getmtime(dest)
                size = os.path.getsize(dest)
            except Exception:
                continue
            kept.append({
                "file": name,
                "mtime": int(mtime),
                "when": human_time(mtime),
                "size": int(size),
                "size_h": human_size(size),
            })
    except Exception:
        pass
    kept.sort(key=lambda x: x.get("mtime", 0), reverse=True)
    kept = kept[:max_photos]
    STATE["photos"] = kept
    stamp_now()
    return kept


def write_ini_kv(path, section, data):
    sections = {}
    current = None
    if os.path.isfile(path):
        try:
            with open(path, "r") as f:
                for raw in f:
                    line = raw.strip()
                    if line.startswith("[") and line.endswith("]"):
                        current = line[1:-1]
                        sections.setdefault(current, [])
                    elif current is not None:
                        sections[current].append(raw.rstrip("\n"))
        except Exception:
            sections = {}
    sections.setdefault(section, [])
    keys_written = set()
    new_lines = []
    for raw in sections[section]:
        if "=" in raw and not raw.strip().startswith(";"):
            k = raw.split("=", 1)[0].strip()
            if k in data:
                new_lines.append("%s=%s" % (k, data[k]))
                keys_written.add(k)
                continue
        new_lines.append(raw)
    for k, v in data.items():
        if k not in keys_written:
            new_lines.append("%s=%s" % (k, v))
    sections[section] = new_lines
    order = []
    if os.path.isfile(path):
        try:
            with open(path, "r") as f:
                for raw in f:
                    line = raw.strip()
                    if line.startswith("[") and line.endswith("]"):
                        name = line[1:-1]
                        if name not in order:
                            order.append(name)
        except Exception:
            pass
    if section not in order:
        order.append(section)
    try:
        with open(path, "w") as f:
            for name in order:
                f.write("[%s]\n" % name)
                for raw in sections.get(name, []):
                    f.write(raw + "\n")
                f.write("\n")
    except Exception as exc:
        print("Could not write ini:", exc)


def read_ini_key(path, section, key, default="0"):
    current = None
    if not os.path.isfile(path):
        return default
    try:
        with open(path, "r") as f:
            for raw in f:
                line = raw.strip()
                if line.startswith("[") and line.endswith("]"):
                    current = line[1:-1]
                elif current == section and "=" in line:
                    k, v = line.split("=", 1)
                    if k.strip() == key:
                        return v.strip()
    except Exception:
        return default
    return default


def lan_ip():
    ip = "127.0.0.1"
    sock = None
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.connect(("8.8.8.8", 80))
        ip = sock.getsockname()[0]
    except Exception:
        try:
            ip = socket.gethostbyname(socket.gethostname())
        except Exception:
            pass
    finally:
        if sock is not None:
            try:
                sock.close()
            except Exception:
                pass
    return ip


def write_open_on_phone(ip, port):
    """Small file next to the bridge so phone URL is easy to find."""
    lan = "http://%s:%s" % (ip, port)
    local = "http://127.0.0.1:%s" % port
    body = (
        "GroveLink — open on your phone (same Wi-Fi as this PC)\n"
        "======================================================\n"
        "\n"
        "  PHONE (LAN):  %s\n"
        "  THIS PC:      %s\n"
        "\n"
        "Keep START_GROVELINK / this bridge window open while you play.\n"
        "In GTA: K → Camera → Enter or Space.\n"
        "\n"
        "Health check: %s/health\n"
    ) % (lan, local, local)
    try:
        with open(OPEN_PHONE_TXT, "w") as f:
            f.write(body)
        print("Wrote URL file:", OPEN_PHONE_TXT)
    except Exception as exc:
        print("Could not write OPEN_ON_PHONE.txt:", exc)


def try_open_browser(url):
    """Fail-soft: open default browser to localhost page."""
    try:
        if sys.platform.startswith("win"):
            try:
                os.startfile(url)  # noqa: PTH118 — Win7 bridge
                return True
            except Exception:
                pass
        if webbrowser is not None:
            webbrowser.open(url)
            return True
    except Exception as exc:
        print("Could not open browser:", exc)
    return False


# HTML is assembled with placeholders for URLs injected at request time via
# a thin wrapper — keep static shell + JS that pulls /api for live data.
HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">
<meta name=\"theme-color\" content=\"#071109\">
<meta name=\"apple-mobile-web-app-capable\" content=\"yes\">
<meta name=\"mobile-web-app-capable\" content=\"yes\">
<title>GroveLink</title>
<style>
  body { margin:0; background:#070b08; color:#d7ffd0; font-family: Arial, Helvetica, sans-serif; }
  .shell { max-width: 440px; margin: 0 auto; min-height: 100vh; background:#10180f; }
  header { padding:16px; background:#071109; border-bottom:2px solid #2cff6a; }
  h1 { margin:0; font-size:18px; letter-spacing:3px; color:#2cff6a; }
  .sub { font-size:12px; color:#7aaa7a; margin-top:6px; line-height:1.5; }
  .urls { margin-top:10px; font-size:12px; color:#b6e6b0; word-break:break-all; }
  .urls strong { color:#2cff6a; }
  .urlrow { display:flex; gap:8px; align-items:flex-start; margin-top:6px; }
  .urlrow span { flex:1; }
  .copybtn, .actionbtn {
    flex:0 0 auto; background:#1a3; color:#d7ffd0; border:1px solid #2cff6a;
    padding:10px 12px; font-size:13px; font-weight:bold; min-height:44px; cursor:pointer;
    text-decoration:none; display:inline-flex; align-items:center; justify-content:center;
    box-sizing:border-box;
  }
  .actionbtn { background:#143; margin:0; }
  .actionbtn[disabled] { opacity:0.4; pointer-events:none; }
  .actions { display:flex; gap:8px; margin-top:10px; flex-wrap:wrap; }
  .actions .actionbtn { flex:1; min-width:140px; }
  .bigcopy {
    margin-top:12px; padding:14px; background:#0b1a0e; border:2px solid #2cff6a;
    border-radius:4px; text-align:center; cursor:pointer; user-select:all;
  }
  .bigcopy .label { font-size:11px; color:#7aaa7a; letter-spacing:1px; }
  .bigcopy .ipport {
    font-size:22px; font-weight:bold; color:#2cff6a; margin:8px 0 4px;
    word-break:break-all; letter-spacing:1px;
  }
  .bigcopy .hint { font-size:11px; color:#7aaa7a; }
  .smsnote { margin-top:8px; font-size:11px; color:#7aaa7a; line-height:1.45; }
  .smsnote a { color:#2cff6a; }
  .searchrow { display:flex; gap:8px; padding:8px 12px 0; align-items:center; }
  .searchrow input {
    flex:1; padding:12px; border:1px solid #2cff6a; background:#0b0f0c; color:#d7ffd0;
    font-size:15px; min-height:44px; box-sizing:border-box;
  }
  .tabs { display:flex; gap:0; margin:8px 12px 0; border:1px solid #1a4; }
  .tab {
    flex:1; background:#0b0f0c; color:#7aaa7a; border:0; border-right:1px solid #1a4;
    padding:12px; font-size:13px; font-weight:bold; min-height:44px; cursor:pointer;
  }
  .tab:last-child { border-right:0; }
  .tab.on { background:#143; color:#2cff6a; }
  .chips { display:flex; gap:8px; padding:0 12px 8px; flex-wrap:wrap; }
  .chip {
    background:#1a2a1a; color:#d7ffd0; border:1px solid #2cff6a; padding:10px 12px;
    font-size:12px; font-weight:bold; min-height:40px; cursor:pointer; border-radius:20px;
  }
  .tip { margin-top:10px; font-size:11px; color:#7aaa7a; line-height:1.45; }
  .tip strong { color:#2cff6a; }
  .status { margin-top:8px; font-size:11px; color:#7aaa7a; }
  .status .ok { color:#2cff6a; }
  .status .bad { color:#ff6a6a; }
  .pulse { display:inline-block; width:10px; height:10px; border-radius:50%; background:#445; margin-right:6px; vertical-align:middle; }
  .pulse.live {
    background:#2cff6a;
    box-shadow:0 0 0 0 rgba(44,255,106,0.55);
    animation: glPulse 1.4s ease-out infinite;
  }
  .pulse.dim { background:#445; box-shadow:none; animation:none; }
  @keyframes glPulse {
    0% { box-shadow:0 0 0 0 rgba(44,255,106,0.55); }
    70% { box-shadow:0 0 0 10px rgba(44,255,106,0); }
    100% { box-shadow:0 0 0 0 rgba(44,255,106,0); }
  }
  .livebadge {
    display:inline-block; margin-left:8px; padding:2px 8px; border:1px solid #2cff6a;
    color:#2cff6a; font-size:10px; letter-spacing:2px; font-weight:bold; vertical-align:middle;
  }
  .livebadge.off { border-color:#a44; color:#ff6a6a; }
  .stats {
    margin-top:10px; display:flex; gap:10px; flex-wrap:wrap;
  }
  .stat {
    flex:1; min-width:110px; background:#0b1a0e; border:1px solid #1a4; padding:10px 12px;
  }
  .stat .k { font-size:10px; color:#7aaa7a; letter-spacing:1px; }
  .stat .v { font-size:20px; font-weight:bold; color:#2cff6a; margin-top:4px; }
  .offline {
    display:none; margin:0; padding:14px 16px; background:#3a1212; border-bottom:2px solid #ff6a6a;
    color:#ffb0b0; font-size:14px; font-weight:bold; line-height:1.4; text-align:center;
  }
  .offline.show { display:block; }
  form { display:flex; gap:8px; padding:12px; position:sticky; top:0; background:#10180f; z-index:2; }
  input[type=text] {
    flex:1; padding:14px; border:1px solid #2cff6a; background:#0b0f0c; color:#d7ffd0;
    font-size:16px; min-height:48px; box-sizing:border-box;
  }
  button.send {
    background:#2cff6a; color:#041006; border:0; padding:14px 18px; font-weight:bold;
    font-size:16px; min-height:48px; min-width:88px;
  }
  .okmsg { padding:0 12px 8px; color:#2cff6a; font-size:12px; min-height:16px; }
  .shot { margin:12px; background:#000; border:1px solid #1a4; position:relative; }
  .shot.unread { border-color:#2cff6a; box-shadow:0 0 0 2px rgba(44,255,106,0.35); }
  .badge {
    position:absolute; top:8px; left:8px; background:#2cff6a; color:#041006;
    font-size:10px; font-weight:bold; padding:4px 8px; letter-spacing:1px; z-index:1;
  }
  .shot a.imgwrap { display:block; }
  .shot img { width:100%; display:block; cursor:zoom-in; }
  .meta { padding:8px 10px; font-size:11px; color:#7aaa7a; display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
  .meta .grow { flex:1; min-width:120px; }
  .delbtn {
    background:#3a1212; color:#ffb0b0; border:1px solid #a44; padding:10px 12px;
    font-size:12px; font-weight:bold; min-height:40px; cursor:pointer;
  }
  .empty { padding:20px 16px; color:#7aaa7a; line-height:1.55; }
  .empty h2 { margin:0 0 10px; color:#2cff6a; font-size:14px; letter-spacing:1px; }
  .empty ol { margin:0; padding-left:20px; }
  .empty li { margin:6px 0; }
  #lightbox {
    display:none; position:fixed; inset:0; background:rgba(0,0,0,0.92);
    z-index:99; align-items:center; justify-content:center; padding:12px;
  }
  #lightbox.show { display:flex; }
  #lightbox img { max-width:100%; max-height:100%; }
  #lightbox .close {
    position:absolute; top:10px; right:14px; color:#2cff6a; font-size:28px;
    background:none; border:0; cursor:pointer; min-width:44px; min-height:44px;
  }
  .empty-lan {
    margin:14px 0 18px; padding:18px 14px; background:#0b1a0e; border:2px solid #2cff6a;
    border-radius:4px; text-align:center; cursor:pointer; user-select:all;
  }
  .empty-lan .label { font-size:11px; color:#7aaa7a; letter-spacing:1px; }
  .empty-lan .ipport {
    font-size:26px; font-weight:bold; color:#2cff6a; margin:10px 0 6px;
    word-break:break-all; letter-spacing:1px; line-height:1.2;
  }
  .empty-lan .hint { font-size:12px; color:#7aaa7a; }
  #confirm_dlg {
    display:none; position:fixed; inset:0; background:rgba(0,0,0,0.82);
    z-index:100; align-items:center; justify-content:center; padding:16px;
  }
  #confirm_dlg.show { display:flex; }
  #confirm_dlg .panel {
    width:100%; max-width:360px; background:#10180f; border:2px solid #2cff6a;
    padding:22px 18px; text-align:center; box-sizing:border-box;
  }
  #confirm_dlg h2 { margin:0 0 8px; color:#2cff6a; font-size:18px; letter-spacing:1px; }
  #confirm_dlg p { margin:0 0 18px; color:#7aaa7a; font-size:13px; line-height:1.45; }
  #confirm_dlg .btns { display:flex; gap:12px; }
  #confirm_dlg .btns button {
    flex:1; min-height:56px; font-size:17px; font-weight:bold; border:0; cursor:pointer;
    padding:14px 12px; -webkit-tap-highlight-color:transparent;
  }
  #confirm_dlg .btn-yes { background:#3a1212; color:#ffb0b0; border:2px solid #a44 !important; }
  #confirm_dlg .btn-no { background:#2cff6a; color:#041006; }
</style>
</head>
<body>
<div class=\"shell\">
  <div class=\"offline\" id=\"offline_banner\">Bridge offline — run START_GROVELINK</div>
  <header>
    <h1>GROVELINK <span class=\"livebadge\" id=\"livebadge\">LIVE</span></h1>
    <div class=\"sub\">Photos from GTA San Andreas on this PC → your real phone</div>
    <div class=\"stats\">
      <div class=\"stat\"><div class=\"k\">VERSION</div><div class=\"v\" id=\"ver\">__VERSION__</div></div>
      <div class=\"stat\"><div class=\"k\">PHOTOS</div><div class=\"v\" id=\"count\">0</div></div>
    </div>
    <div class=\"urls\">
      <div class=\"urlrow\">
        <span><strong>Phone (LAN):</strong> <span id=\"lan_url\">__LAN_URL__</span></span>
        <button type=\"button\" class=\"copybtn\" id=\"copy_lan\">Copy</button>
      </div>
      <div class=\"urlrow\">
        <span><strong>This PC:</strong> <span id=\"local_url\">__LOCAL_URL__</span></span>
        <button type=\"button\" class=\"copybtn\" id=\"copy_local\">Copy</button>
      </div>
    </div>
    <div class=\"actions\">
      <a class=\"actionbtn\" id=\"dl_latest\" href=\"#\" target=\"_blank\" rel=\"noopener\">Download latest</a>
      <a class=\"actionbtn\" id=\"export_zip\" href=\"/export.zip\">Export zip</a>
      <button type=\"button\" class=\"actionbtn\" id=\"mark_read\">Mark all read</button>
      <button type=\"button\" class=\"actionbtn\" id=\"clear_all\" style=\"background:#3a1212;border-color:#a44;color:#ffb0b0\">Clear all phone copies</button>
    </div>
    <div class=\"bigcopy\" id=\"big_copy\" title=\"Tap to copy IP:port\">
      <div class=\"label\">TAP TO COPY — PHONE ADDRESS</div>
      <div class=\"ipport\" id=\"ip_port\">__IP_PORT__</div>
      <div class=\"hint\" id=\"big_copy_hint\">Copies host:port for your phone browser</div>
    </div>
    <div class=\"smsnote\">No QR lib needed — open <code>http://</code> + the address above on your phone (same Wi-Fi). Or text yourself: <a id=\"sms_link\" href=\"#\">sms: note with URL</a>.</div>
    <div class=\"tip\"><strong>Tip:</strong> On your phone, use the browser menu → <b>Add to Home Screen</b> for a one-tap GroveLink icon (no app install / no favicon needed). Theme color matches this green HUD.</div>
    <div class=\"status\" id=\"skip_note\" style=\"display:none;margin-top:6px\">Hidden from phone: <span id=\"skip_count\">0</span> (deleted skip list — Gallery untouched)</div>
    <div class=\"status\">
      <span class=\"pulse live\" id=\"pulse\"></span>
      Bridge: <span id=\"bridge_status\" class=\"ok\">online</span>
      &nbsp;·&nbsp; Last poll: <span id=\"last_refresh\">—</span>
      &nbsp;·&nbsp; <span id=\"refresh_hint\">auto every 2s</span>
      &nbsp;·&nbsp; Unread: <span id=\"unread_count\">0</span>
      <span id=\"last_error_hint\" class=\"bad\" style=\"display:none\"></span>
    </div>
  </header>
  <form id=\"f\">
    <input id=\"msg\" type=\"text\" maxlength=\"80\" placeholder=\"Message to CJ...\" required>
    <button class=\"send\" type=\"submit\">SEND</button>
  </form>
  <div class=\"chips\">
    <button type=\"button\" class=\"chip\" data-msg=\"Where you at?\">Where you at?</button>
    <button type=\"button\" class=\"chip\" data-msg=\"Nice shot\">Nice shot</button>
    <button type=\"button\" class=\"chip\" data-msg=\"Come to Grove\">Come to Grove</button>
  </div>
  <div class=\"okmsg\" id=\"ok\"></div>
  <div class=\"searchrow\">
    <input id=\"search\" type=\"search\" placeholder=\"Search filename...\" autocomplete=\"off\">
  </div>
  <div class=\"tabs\">
    <button type=\"button\" class=\"tab on\" id=\"tab_all\" data-filter=\"all\">All</button>
    <button type=\"button\" class=\"tab\" id=\"tab_today\" data-filter=\"today\">Today</button>
    <button type=\"button\" class=\"tab\" id=\"tab_sort\" data-sort=\"newest\" title=\"Client-side only — server always sends newest first\">Newest</button>
  </div>
  <div id=\"feed\"></div>
</div>
<div id=\"lightbox\" onclick=\"closeLb(event)\">
  <button type=\"button\" class=\"close\" onclick=\"closeLb(event)\">&times;</button>
  <img id=\"lbimg\" src=\"\" alt=\"full size\">
</div>
<div id=\"confirm_dlg\" onclick=\"confirmCancel(event)\">
  <div class=\"panel\" onclick=\"event.stopPropagation()\">
    <h2>Delete this shot?</h2>
    <p id=\"confirm_detail\">Removes it from the phone page only.<br>GTA Gallery file stays on the PC.</p>
    <div class=\"btns\">
      <button type=\"button\" class=\"btn-no\" id=\"confirm_no\">Cancel</button>
      <button type=\"button\" class=\"btn-yes\" id=\"confirm_yes\">Delete</button>
    </div>
  </div>
</div>
<script>
var LS_KEY = 'grovelink_last_visit';
var FILTER = 'all';
var SEARCH_Q = '';
var SORT_ORDER = 'newest'; // client-side only; server /api is always newest-first
var LAST_PHOTOS = [];
var PENDING_ACTION = ''; // 'delete:NAME' or 'clear'
function emptyHtml() {
  var ipPort = '';
  try { ipPort = (document.getElementById('ip_port') || {}).textContent || ''; } catch (e) {}
  return '<div class=\"empty\">' +
    '<h2>NO PHOTOS YET</h2>' +
    '<div class=\"empty-lan\" id=\"empty_lan_copy\" title=\"Tap to copy\">' +
    '<div class=\"label\">FIRST VISIT — OPEN ON YOUR PHONE</div>' +
    '<div class=\"ipport\">' + escapeHtml(ipPort) + '</div>' +
    '<div class=\"hint\">Tap to copy · same Wi-Fi as this PC · keep Copy above too</div>' +
    '</div>' +
    '<ol>' +
    '<li>Run <b>GroveLink Phone</b> / <b>START_GROVELINK</b> on the PC (keep the window open).</li>' +
    '<li>On your phone open <b>http://</b> + the address above (or use Copy).</li>' +
    '<li>In GTA press <b>K</b> → <b>Camera</b> → <b>Enter</b> or <b>Space</b>.</li>' +
    '<li>Phone and PC must be on the <b>same Wi-Fi</b>.</li>' +
    '</ol>' +
    '</div>';
}
var EMPTY_TODAY =
  '<div class=\"empty\">' +
  '<h2>NO SHOTS TODAY</h2>' +
  '<p>Switch to <b>All</b>, or take a new photo in GTA (K → Camera → Enter).</p>' +
  '</div>';
function bindEmptyLanCopy() {
  var el = document.getElementById('empty_lan_copy');
  if (!el) return;
  el.onclick = function() {
    var t = document.getElementById('ip_port').textContent;
    copyText(t, null);
    var hint = el.querySelector('.hint');
    if (hint) {
      var old = hint.textContent;
      hint.textContent = 'Copied! Open http://' + t + ' on your phone';
      setTimeout(function(){ hint.textContent = old; }, 2000);
    }
  };
}

function escapeHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\"/g,'&quot;');
}

function getLastVisit() {
  try {
    var v = parseInt(localStorage.getItem(LS_KEY) || '0', 10);
    return isNaN(v) ? 0 : v;
  } catch (e) { return 0; }
}
function setLastVisit(ts) {
  try { localStorage.setItem(LS_KEY, String(ts || Math.floor(Date.now()/1000))); } catch (e) {}
}

function startOfTodaySec() {
  var d = new Date();
  d.setHours(0,0,0,0);
  return Math.floor(d.getTime() / 1000);
}

function copyText(text, btn) {
  function ok() {
    if (!btn) return;
    var old = btn.textContent;
    btn.textContent = 'Copied!';
    setTimeout(function(){ btn.textContent = old; }, 1500);
  }
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).then(ok).catch(function(){ fallback(); });
  } else {
    fallback();
  }
  function fallback() {
    var ta = document.createElement('textarea');
    ta.value = text;
    document.body.appendChild(ta);
    ta.select();
    try { document.execCommand('copy'); ok(); } catch (e) {}
    document.body.removeChild(ta);
  }
}

function openLb(src) {
  var box = document.getElementById('lightbox');
  document.getElementById('lbimg').src = src;
  box.className = 'show';
}
function closeLb(ev) {
  if (ev) ev.stopPropagation();
  var box = document.getElementById('lightbox');
  box.className = '';
  document.getElementById('lbimg').src = '';
}

var PENDING_DELETE = '';
function confirmCancel(ev) {
  if (ev) ev.stopPropagation();
  PENDING_DELETE = '';
  PENDING_ACTION = '';
  var dlg = document.getElementById('confirm_dlg');
  if (dlg) dlg.className = '';
}
function setConfirmCopy(title, detail, yesLabel) {
  var h = document.querySelector('#confirm_dlg h2');
  var p = document.getElementById('confirm_detail');
  var y = document.getElementById('confirm_yes');
  if (h) h.textContent = title || 'Delete this shot?';
  if (p) p.innerHTML = detail || 'Removes it from the phone page only.<br>GTA Gallery file stays on the PC.';
  if (y) y.textContent = yesLabel || 'Delete';
}
function confirmYes() {
  var action = PENDING_ACTION;
  var name = PENDING_DELETE;
  confirmCancel();
  if (action === 'clear') { doClearAll(); return; }
  if (!name) return;
  doDeletePhoto(name);
}
function deletePhoto(name) {
  if (!name) return;
  PENDING_ACTION = 'delete';
  PENDING_DELETE = name;
  setConfirmCopy('Delete this shot?', 'Removes it from the phone page only.<br>GTA Gallery file stays on the PC.', 'Delete');
  var dlg = document.getElementById('confirm_dlg');
  if (dlg) dlg.className = 'show';
}
function clearAllPhotos() {
  PENDING_ACTION = 'clear';
  PENDING_DELETE = '';
  setConfirmCopy('Clear all phone copies?', 'Deletes every shot under bridge/photos only.<br>GTA Gallery on the PC is NOT touched.', 'Clear all');
  var dlg = document.getElementById('confirm_dlg');
  if (dlg) dlg.className = 'show';
}
function doClearAll() {
  var x = new XMLHttpRequest();
  x.open('POST', '/clear', true);
  x.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
  x.onreadystatechange = function() {
    if (x.readyState === 4) {
      var okEl = document.getElementById('ok');
      if (x.status === 200) {
        try {
          var j = JSON.parse(x.responseText);
          okEl.textContent = 'Cleared ' + (j.cleared || 0) + ' phone copies (Gallery untouched).';
        } catch (e) { okEl.textContent = 'Cleared phone copies.'; }
        poll();
      } else {
        okEl.textContent = 'Clear failed.';
      }
      setTimeout(function(){ okEl.textContent = ''; }, 3000);
    }
  };
  x.send('confirm=1');
}
function doDeletePhoto(name) {
  var body = 'file=' + encodeURIComponent(name);
  var x = new XMLHttpRequest();
  x.open('POST', '/delete', true);
  x.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
  x.onreadystatechange = function() {
    if (x.readyState === 4) {
      var okEl = document.getElementById('ok');
      if (x.status === 200) {
        okEl.textContent = 'Removed from phone page (GTA Gallery untouched).';
        poll();
      } else {
        okEl.textContent = 'Could not delete (already gone?).';
      }
      setTimeout(function(){ okEl.textContent = ''; }, 3000);
    }
  };
  x.send(body);
}
function sendMsg(msg) {
  msg = (msg || '').trim();
  if (!msg) return;
  var body = 'msg=' + encodeURIComponent(msg);
  var x = new XMLHttpRequest();
  x.open('POST', '/send', true);
  x.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
  x.onreadystatechange = function() {
    if (x.readyState === 4) {
      document.getElementById('ok').textContent = 'Sent to CJ — open INBOX on the in-game phone.';
      document.getElementById('msg').value = '';
      setTimeout(function(){ document.getElementById('ok').textContent = ''; }, 3000);
    }
  };
  x.send(body);
}

function setFilter(f) {
  FILTER = f;
  var all = document.getElementById('tab_all');
  var today = document.getElementById('tab_today');
  if (all) all.className = (f === 'all') ? 'tab on' : 'tab';
  if (today) today.className = (f === 'today') ? 'tab on' : 'tab';
  renderFeed(LAST_PHOTOS);
}

function renderFeed(photos) {
  var feed = document.getElementById('feed');
  var lastVisit = getLastVisit();
  var unread = 0;
  var today0 = startOfTodaySec();
  var list = photos || [];
  if (FILTER === 'today') {
    var filtered = [];
    for (var j = 0; j < list.length; j++) {
      var mt = parseInt(list[j].mtime || 0, 10) || 0;
      if (mt >= today0) filtered.push(list[j]);
    }
    list = filtered;
  }
  if (SEARCH_Q) {
    var q = SEARCH_Q.toLowerCase();
    var filtered2 = [];
    for (var k = 0; k < list.length; k++) {
      var nm = String(list[k].file || list[k] || '').toLowerCase();
      if (nm.indexOf(q) >= 0) filtered2.push(list[k]);
    }
    list = filtered2;
  }
  // Client-side sort toggle (server always returns newest-first)
  if (SORT_ORDER === 'oldest') {
    list = list.slice().reverse();
  }
  if (!photos || !photos.length) {
    document.getElementById('unread_count').textContent = '0';
    feed.innerHTML = emptyHtml();
    bindEmptyLanCopy();
    return;
  }
  if (!list.length) {
    document.getElementById('unread_count').textContent = '0';
    if (SEARCH_Q) {
      feed.innerHTML = '<div class=\"empty\"><h2>NO MATCHES</h2><p>No filenames match <b>' + escapeHtml(SEARCH_Q) + '</b>. Clear the search box.</p></div>';
    } else {
      feed.innerHTML = EMPTY_TODAY;
    }
    return;
  }
  var html = '';
  for (var i = 0; i < list.length && i < 40; i++) {
    var p = list[i];
    var name = p.file || p;
    var when = p.when || '';
    var mtime = parseInt(p.mtime || 0, 10) || 0;
    var sizeH = p.size_h || '';
    var isNew = mtime > lastVisit;
    if (isNew) unread++;
    var href = '/photo/' + name;
    html += '<div class=\"shot' + (isNew ? ' unread' : '') + '\">';
    if (isNew) html += '<div class=\"badge\">NEW</div>';
    html += '<a class=\"imgwrap\" href=\"' + href + '\" target=\"_blank\" rel=\"noopener\" onclick=\"openLb(\\'' + href + '\\'); return false;\">';
    html += '<img src=\"' + href + '\" alt=\"shot\">';
    html += '</a>';
    var metaBits = [];
    if (when) metaBits.push(when);
    if (sizeH) metaBits.push(sizeH);
    metaBits.push(name);
    html += '<div class=\"meta\"><span class=\"grow\">' + escapeHtml(metaBits.join(' · ')) +
            ' · <a href=\"' + href + '\" target=\"_blank\" rel=\"noopener\">full size</a></span>';
    html += '<button type=\"button\" class=\"delbtn\" onclick=\"deletePhoto(\\'' + String(name).replace(/'/g, '') + '\\')\">Delete</button>';
    html += '</div></div>';
  }
  document.getElementById('unread_count').textContent = String(unread);
  feed.innerHTML = html;
}

function paint(data) {
  var count = document.getElementById('count');
  var photos = data.photos || [];
  LAST_PHOTOS = photos;
  count.textContent = (typeof data.count === 'number') ? data.count : photos.length;
  var lr = data.last_refresh_human || data.last_refresh || '—';
  document.getElementById('last_refresh').textContent = lr;
  if (data.version) {
    var verEl = document.getElementById('ver');
    if (verEl) verEl.textContent = data.version;
  }
  var st = document.getElementById('bridge_status');
  var pulse = document.getElementById('pulse');
  var badge = document.getElementById('livebadge');
  var ban = document.getElementById('offline_banner');
  var bridgeOk = (data.bridge_ok !== false) && (data.ok !== false);
  if (!bridgeOk) {
    st.textContent = 'offline';
    st.className = 'bad';
    pulse.className = 'pulse dim';
    if (badge) { badge.textContent = 'OFF'; badge.className = 'livebadge off'; }
    if (ban) ban.className = 'offline show';
  } else {
    st.textContent = 'online';
    st.className = 'ok';
    pulse.className = 'pulse live';
    if (badge) { badge.textContent = 'LIVE'; badge.className = 'livebadge'; }
    if (ban) ban.className = 'offline';
  }
  if (typeof data.poll_ms === 'number' && data.poll_ms >= 500) {
    POLL_MS = data.poll_ms;
  }
  var errHint = document.getElementById('last_error_hint');
  if (errHint) {
    if (data.last_error) {
      errHint.textContent = ' · err: ' + data.last_error;
      errHint.style.display = '';
    } else {
      errHint.textContent = '';
      errHint.style.display = 'none';
    }
  }
  var skipNote = document.getElementById('skip_note');
  var skipCount = document.getElementById('skip_count');
  var skipped = parseInt(data.skipped_deleted || 0, 10) || 0;
  if (skipNote && skipCount) {
    if (skipped > 0) {
      skipCount.textContent = String(skipped);
      skipNote.style.display = '';
    } else {
      skipCount.textContent = '0';
      skipNote.style.display = 'none';
    }
  }
  if (data.lan_url) document.getElementById('lan_url').textContent = data.lan_url;
  if (data.local_url) document.getElementById('local_url').textContent = data.local_url;
  var ipPort = (data.ip || '') + ':' + (data.port || '');
  if (data.ip) {
    document.getElementById('ip_port').textContent = ipPort;
    var sms = document.getElementById('sms_link');
    if (sms) {
      var note = 'GroveLink phone page: ' + (data.lan_url || ('http://' + ipPort));
      sms.href = 'sms:?&body=' + encodeURIComponent(note);
    }
  }

  var latest = data.latest || (photos[0] && (photos[0].file || photos[0])) || '';
  var dl = document.getElementById('dl_latest');
  if (latest) {
    dl.href = '/photo/' + latest;
    dl.removeAttribute('disabled');
    dl.style.opacity = '1';
    dl.style.pointerEvents = 'auto';
  } else {
    dl.href = '#';
    dl.setAttribute('disabled', 'disabled');
    dl.style.opacity = '0.4';
    dl.style.pointerEvents = 'none';
  }
  renderFeed(photos);
}
var POLL_MS = 2000;
var POLL_TIMER = null;
function setOfflineUI(reason) {
  var st = document.getElementById('bridge_status');
  var pulse = document.getElementById('pulse');
  var badge = document.getElementById('livebadge');
  var ban = document.getElementById('offline_banner');
  if (st) { st.textContent = 'offline'; st.className = 'bad'; }
  if (pulse) pulse.className = 'pulse dim';
  if (badge) { badge.textContent = 'OFF'; badge.className = 'livebadge off'; }
  if (ban) ban.className = 'offline show';
  var hint = document.getElementById('refresh_hint');
  if (hint) hint.textContent = reason || 'reconnect...';
}
function poll() {
  var x = new XMLHttpRequest();
  x.open('GET', '/api', true);
  x.timeout = Math.max(3000, POLL_MS + 1000);
  x.onreadystatechange = function() {
    if (x.readyState !== 4) return;
    if (x.status === 200) {
      try { paint(JSON.parse(x.responseText)); } catch (e) { setOfflineUI('bad JSON'); return; }
      var hint = document.getElementById('refresh_hint');
      if (hint) {
        var secs = Math.round(POLL_MS / 1000);
        if (secs < 1) secs = 1;
        hint.textContent = 'updated';
        setTimeout(function(){ hint.textContent = 'auto every ' + secs + 's'; }, 800);
      }
    } else {
      setOfflineUI('Bridge offline — run START_GROVELINK');
    }
  };
  x.ontimeout = function() { setOfflineUI('Bridge offline — run START_GROVELINK'); };
  x.onerror = function() { setOfflineUI('Bridge offline — run START_GROVELINK'); };
  try { x.send(); } catch (e) { setOfflineUI('Bridge offline — run START_GROVELINK'); }
}
function schedulePoll() {
  if (POLL_TIMER) clearTimeout(POLL_TIMER);
  POLL_TIMER = setTimeout(function(){ poll(); schedulePoll(); }, POLL_MS);
}
document.getElementById('copy_lan').onclick = function() {
  copyText(document.getElementById('lan_url').textContent, this);
};
document.getElementById('copy_local').onclick = function() {
  copyText(document.getElementById('local_url').textContent, this);
};
document.getElementById('big_copy').onclick = function() {
  var t = document.getElementById('ip_port').textContent;
  copyText(t, null);
  var hint = document.getElementById('big_copy_hint');
  var old = hint.textContent;
  hint.textContent = 'Copied! Open http://' + t + ' on your phone';
  setTimeout(function(){ hint.textContent = old; }, 2000);
};
document.getElementById('tab_all').onclick = function() { setFilter('all'); };
document.getElementById('tab_today').onclick = function() { setFilter('today'); };
(function() {
  var btn = document.getElementById('tab_sort');
  if (!btn) return;
  btn.onclick = function() {
    SORT_ORDER = (SORT_ORDER === 'newest') ? 'oldest' : 'newest';
    btn.setAttribute('data-sort', SORT_ORDER);
    btn.textContent = (SORT_ORDER === 'newest') ? 'Newest' : 'Oldest';
    btn.className = 'tab on';
    renderFeed(LAST_PHOTOS);
  };
})();
(function() {
  var s = document.getElementById('search');
  if (!s) return;
  var t = null;
  s.oninput = function() {
    SEARCH_Q = (s.value || '').trim();
    if (t) clearTimeout(t);
    t = setTimeout(function(){ renderFeed(LAST_PHOTOS); }, 120);
  };
})();
document.getElementById('clear_all').onclick = function() { clearAllPhotos(); };
(function() {
  var chips = document.querySelectorAll('.chip');
  for (var i = 0; i < chips.length; i++) {
    chips[i].onclick = function() {
      var m = this.getAttribute('data-msg') || this.textContent;
      document.getElementById('msg').value = m;
      sendMsg(m);
    };
  }
})();
document.getElementById('mark_read').onclick = function() {
  setLastVisit(Math.floor(Date.now()/1000));
  poll();
  var okEl = document.getElementById('ok');
  okEl.textContent = 'Marked all as read.';
  setTimeout(function(){ okEl.textContent = ''; }, 2000);
};
document.getElementById('f').onsubmit = function(ev) {
  ev.preventDefault();
  sendMsg(document.getElementById('msg').value);
};
if (!getLastVisit()) {
  try { /* leave 0 so existing shots show NEW on first open */ } catch (e) {}
}
document.getElementById('confirm_yes').onclick = function(ev){ if(ev)ev.stopPropagation(); confirmYes(); };
document.getElementById('confirm_no').onclick = function(ev){ if(ev)ev.stopPropagation(); confirmCancel(ev); };
document.getElementById('feed').innerHTML = emptyHtml();
bindEmptyLanCopy();
poll();
schedulePoll();
</script>
</body>
</html>
"""



def render_html():
    ip = STATE.get("ip", "127.0.0.1")
    port = STATE.get("port", 8088)
    lan = "http://%s:%s" % (ip, port)
    local = "http://127.0.0.1:%s" % port
    ip_port = "%s:%s" % (ip, port)
    ver = STATE.get("version", "unknown") or "unknown"
    return (
        HTML_TEMPLATE
        .replace("__LAN_URL__", lan)
        .replace("__LOCAL_URL__", local)
        .replace("__IP_PORT__", ip_port)
        .replace("__VERSION__", ver)
    )


def render_qr_page():
    """No QR dependency — large tap-to-copy IP:port + sms-style note."""
    ip = STATE.get("ip", "127.0.0.1")
    port = STATE.get("port", 8088)
    lan = "http://%s:%s" % (ip, port)
    ip_port = "%s:%s" % (ip, port)
    sms_body = "GroveLink phone page: %s" % lan
    # Keep HTML simple, stdlib only, no SVG QR
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>GroveLink — share URL</title>"
        "<style>"
        "body{margin:0;background:#070b08;color:#d7ffd0;font-family:Arial,sans-serif;}"
        ".box{max-width:440px;margin:40px auto;padding:20px;text-align:center;}"
        "h1{color:#2cff6a;letter-spacing:2px;font-size:18px;}"
        ".ip{font-size:28px;font-weight:bold;color:#2cff6a;margin:24px 0;padding:20px;"
        "border:2px solid #2cff6a;cursor:pointer;word-break:break-all;}"
        "a{color:#2cff6a;} p{color:#7aaa7a;line-height:1.5;font-size:13px;}"
        "</style></head><body><div class=\"box\">"
        "<h1>GROVELINK</h1>"
        "<p>No QR code library — tap the address to copy, then open it on your phone "
        "(same Wi-Fi as this PC).</p>"
        "<div class=\"ip\" id=\"c\" onclick=\"var t=this.textContent;"
        "if(navigator.clipboard)navigator.clipboard.writeText(t);"
        "else{var a=document.createElement('textarea');a.value=t;document.body.appendChild(a);"
        "a.select();document.execCommand('copy');document.body.removeChild(a);}"
        "this.style.background='#143';\">%s</div>"
        "<p>Full URL: <a href=\"%s\">%s</a></p>"
        "<p><a href=\"sms:?&amp;body=%s\">Text yourself this URL (sms:)</a></p>"
        "<p><a href=\"/\">&larr; Back to GroveLink</a></p>"
        "</div></body></html>"
    ) % (
        ip_port,
        lan,
        lan,
        # url-encode lightly for href
        sms_body.replace(" ", "%20").replace(":", "%3A").replace("/", "%2F"),
    )


def api_payload():
    ip = STATE.get("ip", "127.0.0.1")
    port = STATE.get("port", 8088)
    photos = STATE.get("photos", [])
    latest = ""
    if photos:
        latest = photos[0].get("file") or ""
    return {
        "ok": True,
        "bridge_ok": bool(STATE.get("bridge_ok", True)),
        "photos": photos,
        "inbox": STATE.get("inbox", []),
        "photo_count": len(photos),
        "count": len(photos),
        "latest": latest,
        "last_refresh": STATE.get("last_refresh", 0),
        "last_refresh_human": STATE.get("last_refresh_human", ""),
        "lan_url": "http://%s:%s" % (ip, port),
        "local_url": "http://127.0.0.1:%s" % port,
        "ip": ip,
        "port": port,
        "max_photos": int(STATE.get("max_photos") or 40),
        "poll_ms": int(STATE.get("poll_ms") or 2000),
        "version": STATE.get("version", "unknown") or "unknown",
        "last_error": STATE.get("last_error", "") or "",
        "skipped_deleted": len(DELETED),
    }


def health_payload():
    photos = STATE.get("photos", [])
    latest = ""
    if photos:
        latest = photos[0].get("file") or ""
    return {
        "ok": True,
        "bridge_ok": bool(STATE.get("bridge_ok", True)),
        "photo_count": len(photos),
        "count": len(photos),
        "latest": latest,
        "galleries": list(STATE.get("galleries", [])),
        "ip": STATE.get("ip", "127.0.0.1"),
        "port": STATE.get("port", 8088),
        "gta_dir": STATE.get("gta_dir", "") or "",
        "version": STATE.get("version", "unknown") or "unknown",
        "poll_ms": int(STATE.get("poll_ms") or 2000),
        "max_photos": int(STATE.get("max_photos") or 40),
        "last_error": STATE.get("last_error", "") or "",
        "skipped_deleted": len(DELETED),
    }



def delete_bridge_photo(name):
    """Remove a file from bridge/photos only (never GTA Gallery)."""
    name = os.path.basename(name or "")
    if not name or name in (".", "..") or "/" in name or "\\" in name:
        return False, "bad name"
    # Reject path tricks
    if ".." in name:
        return False, "bad name"
    full = os.path.join(WEB_PHOTOS, name)
    # Must stay inside WEB_PHOTOS
    try:
        web_abs = os.path.abspath(WEB_PHOTOS)
        full_abs = os.path.abspath(full)
        if not full_abs.startswith(web_abs + os.sep) and full_abs != web_abs:
            return False, "bad path"
    except Exception:
        return False, "bad path"
    if not os.path.isfile(full):
        return False, "not found"
    try:
        os.remove(full)
    except Exception as exc:
        return False, str(exc)
    DELETED.add(name)
    save_deleted()
    # Refresh STATE photos list (keep order, drop deleted)
    STATE["photos"] = [p for p in STATE.get("photos", []) if p.get("file") != name]
    stamp_now()
    return True, "deleted"


def clear_all_bridge_photos():
    """Delete every image under bridge/photos only (never GTA Gallery)."""
    removed = 0
    errors = 0
    if not os.path.isdir(WEB_PHOTOS):
        STATE["photos"] = []
        stamp_now()
        return True, 0
    try:
        names = os.listdir(WEB_PHOTOS)
    except Exception as exc:
        STATE["last_error"] = "bridge photos unreadable: %s" % exc
        return False, 0
    for name in names:
        low = name.lower()
        if not (
            low.endswith(".jpg")
            or low.endswith(".jpeg")
            or low.endswith(".png")
            or low.endswith(".bmp")
        ):
            continue
        full = os.path.join(WEB_PHOTOS, name)
        if not os.path.isfile(full):
            continue
        try:
            os.remove(full)
            DELETED.add(name)
            removed += 1
        except Exception:
            errors += 1
    save_deleted()
    STATE["photos"] = []
    stamp_now()
    if errors and not removed:
        return False, 0
    return True, removed


def build_export_zip():
    """Zip contents of bridge/photos (stdlib zipfile). Always valid zip."""
    buf = BytesIO()
    try:
        zf = zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED)
    except RuntimeError:
        zf = zipfile.ZipFile(buf, "w", zipfile.ZIP_STORED)
    try:
        count = 0
        if os.path.isdir(WEB_PHOTOS):
            try:
                names = os.listdir(WEB_PHOTOS)
            except Exception:
                names = []
            for name in sorted(names):
                low = name.lower()
                if not (
                    low.endswith(".jpg")
                    or low.endswith(".jpeg")
                    or low.endswith(".png")
                    or low.endswith(".bmp")
                ):
                    continue
                if name in DELETED:
                    continue
                full = os.path.join(WEB_PHOTOS, name)
                if not os.path.isfile(full):
                    continue
                try:
                    zf.write(full, arcname=name)
                    count += 1
                except Exception:
                    continue
        lines = [
            "GroveLink photo export",
            "Copies from bridge/photos only (GTA Gallery untouched).",
            "Pack version: %s" % (STATE.get("version", "unknown") or "unknown"),
            "Files: %d" % count,
        ]
        zf.writestr("README_GROVELINK.txt", "\n".join(lines) + "\n")
    finally:
        try:
            zf.close()
        except Exception:
            pass
    data = buf.getvalue()
    try:
        buf.close()
    except Exception:
        pass
    return data


class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        return

    def _bytes(self, text):
        if isinstance(text, bytes):
            return text
        return text.encode("utf-8")

    def _html(self, body, code=200):
        data = self._bytes(body)
        self.send_response(code)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(data)

    def _json(self, obj, code=200):
        payload = json.dumps(obj)
        data = self._bytes(payload)
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        qs = ""
        if "?" in self.path:
            qs = self.path.split("?", 1)[1]
        if path == "/" or path == "/index.html":
            if not STATE.get("phone_page_logged"):
                STATE["phone_page_logged"] = True
                print("Phone page opened")
                sys.stdout.flush()
            self._html(render_html())
            return
        if path == "/qr":
            self._html(render_qr_page())
            return
        if path == "/api":
            self._json(api_payload())
            return
        if path == "/health":
            self._json(health_payload())
            return
        if path == "/clear":
            # Careful GET clear?confirm=1  (also POST /clear)
            fields = parse_qs(qs)
            conf = ""
            if "confirm" in fields and fields["confirm"]:
                conf = fields["confirm"][0]
            if conf not in ("1", "yes", "true"):
                self._json({"ok": False, "detail": "confirm=1 required"}, code=400)
                return
            ok, n = clear_all_bridge_photos()
            self._json({"ok": ok, "cleared": n, "detail": "cleared %d" % n})
            return
        if path == "/export.zip":
            try:
                data = build_export_zip()
            except Exception as exc:
                self._json({"ok": False, "detail": str(exc)}, code=500)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/zip")
            self.send_header("Content-Disposition", 'attachment; filename="grovelink-photos.zip"')
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return
        # Careful GET delete: /delete?file=NAME  (also supports POST)
        if path == "/delete":
            fields = parse_qs(qs)
            name = ""
            if "file" in fields and fields["file"]:
                name = fields["file"][0]
            ok, detail = delete_bridge_photo(name)
            self._json({"ok": ok, "detail": detail, "file": os.path.basename(name or "")})
            return
        if path.startswith("/photo/"):
            name = os.path.basename(unquote(path[len("/photo/"):]))
            if not name or name in (".", "..") or ".." in name or "/" in name or "\\" in name:
                self.send_error(404)
                return
            full = os.path.join(WEB_PHOTOS, name)
            try:
                web_abs = os.path.abspath(WEB_PHOTOS)
                full_abs = os.path.abspath(full)
                if not full_abs.startswith(web_abs + os.sep) and full_abs != web_abs:
                    self.send_error(404)
                    return
            except Exception:
                self.send_error(404)
                return
            if not os.path.isfile(full):
                self.send_error(404)
                return
            ext = name.lower().rsplit(".", 1)[-1]
            mime = {
                "jpg": "image/jpeg",
                "jpeg": "image/jpeg",
                "png": "image/png",
                "bmp": "image/bmp",
            }.get(ext, "application/octet-stream")
            try:
                with open(full, "rb") as f:
                    data = f.read()
            except Exception:
                self.send_error(500)
                return
            self.send_response(200)
            self.send_header("Content-Type", mime)
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        self.send_error(404)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            text_body = raw.decode("utf-8")
        except Exception:
            text_body = raw.decode("latin-1")

        if path == "/clear":
            # Require confirm=1 (same as GET /clear) — accidental wipe guard
            conf = ""
            if text_body.lstrip().startswith("{"):
                try:
                    conf = str(json.loads(text_body).get("confirm") or "")
                except Exception:
                    conf = ""
            else:
                fields = parse_qs(text_body)
                if "confirm" in fields and fields["confirm"]:
                    conf = fields["confirm"][0]
            if not conf and "?" in self.path:
                qfields = parse_qs(self.path.split("?", 1)[1])
                if "confirm" in qfields and qfields["confirm"]:
                    conf = qfields["confirm"][0]
            if conf not in ("1", "yes", "true"):
                self._json({"ok": False, "detail": "confirm=1 required"}, code=400)
                return
            ok, n = clear_all_bridge_photos()
            code = 200 if ok else 500
            self._json({"ok": ok, "cleared": n, "detail": "cleared %d" % n}, code=code)
            return

        if path == "/delete":
            name = ""
            if text_body.lstrip().startswith("{"):
                try:
                    name = json.loads(text_body).get("file") or ""
                except Exception:
                    name = ""
            else:
                fields = parse_qs(text_body)
                if "file" in fields and fields["file"]:
                    name = fields["file"][0]
            # Also allow ?file= on POST URL
            if not name and "?" in self.path:
                qfields = parse_qs(self.path.split("?", 1)[1])
                if "file" in qfields and qfields["file"]:
                    name = qfields["file"][0]
            ok, detail = delete_bridge_photo(name)
            code = 200 if ok else 404
            self._json({"ok": ok, "detail": detail, "file": os.path.basename(name or "")}, code=code)
            return

        if path != "/send":
            self.send_error(404)
            return
        msg = ""
        if text_body.lstrip().startswith("{"):
            try:
                msg = json.loads(text_body).get("msg") or ""
            except Exception:
                msg = ""
        else:
            fields = parse_qs(text_body)
            if "msg" in fields and fields["msg"]:
                msg = fields["msg"][0]
        msg = (msg or "").strip().replace("\r", " ").replace("\n", " ")[:80]
        if msg:
            STATE["inbox"].insert(0, msg)
            STATE["inbox"] = STATE["inbox"][:30]
            STATE["sent"] = STATE.get("sent", 0) + 1
            write_ini_kv(self.server.link_ini, "INBOX", {
                "new": "1",
                "from": "REAL PHONE",
                "msg": msg.replace("=", "-"),
            })
            print("SMS -> GTA:", msg)
        self._json({"ok": True})



def shutter_burst(cfg, gta_dir, seconds=3.0, interval=0.25):
    """After PHOTO.take flips, poll/copy aggressively for a few seconds."""
    deadline = time.time() + seconds
    STATE["shutter_burst_until"] = deadline
    while time.time() < deadline:
        try:
            ensure_gallery_dirs(cfg, gta_dir)
            galleries = detect_gallery(cfg, gta_dir)
            STATE["galleries"] = list(galleries)
            copy_latest(galleries)
        except Exception as exc:
            print("burst error:", exc)
        time.sleep(interval)
    STATE["shutter_burst_until"] = 0


def watcher(cfg, gta_dir, ini):
    """Poll Gallery folders forever. Re-detect dirs each loop so a folder
    created after the first in-game photo is picked up (startup may have
    found none). When PHOTO.take=1, burst-poll for faster shutter react."""
    last_galleries = []
    while True:
        try:
            ensure_gallery_dirs(cfg, gta_dir)
            galleries = detect_gallery(cfg, gta_dir)
            STATE["galleries"] = list(galleries)
            if galleries != last_galleries:
                if galleries:
                    print("Galleries now:")
                    for g in galleries:
                        print("   ", g)
                else:
                    print("Galleries  : still none — waiting for folder/photos")
                last_galleries = list(galleries)
            copy_latest(galleries)
            take = read_ini_key(ini, "PHOTO", "take", "0")
            if take == "1":
                write_ini_kv(ini, "PHOTO", {"take": "0"})
                print("Shutter — fast poll for new Gallery files...")
                shutter_burst(cfg, gta_dir, seconds=3.5, interval=0.25)
                print("Shutter done. Phone page has", len(STATE["photos"]), "shots")
                # Race fix: another snap may have set take=1 during burst — loop now
                if read_ini_key(ini, "PHOTO", "take", "0") == "1":
                    continue
        except Exception as exc:
            STATE["last_error"] = "watch error: %s" % exc
            print("watch error:", exc)
        # Idle poll: 1s normally; stay responsive
        time.sleep(1.0)


def main():
    cfg = read_cfg()
    gta_dir = detect_gta_dir(cfg)
    ensure_dirs(cfg, gta_dir)
    load_deleted()
    galleries = detect_gallery(cfg, gta_dir)
    ini = link_ini_path(gta_dir)
    port = 8088
    try:
        port = int(cfg_get(cfg, "server", "port", "8088") or "8088")
    except Exception:
        port = 8088
    max_photos = cfg_int(cfg, "server", "max_photos", 40)
    if max_photos < 1:
        max_photos = 40
    poll_ms = cfg_int(cfg, "server", "poll_ms", 2000)
    if poll_ms < 500:
        poll_ms = 500
    if poll_ms > 60000:
        poll_ms = 60000

    ip = lan_ip()
    STATE["ip"] = ip
    STATE["port"] = port
    STATE["max_photos"] = max_photos
    STATE["poll_ms"] = poll_ms
    STATE["gta_dir"] = gta_dir or ""
    STATE["galleries"] = list(galleries)
    STATE["bridge_ok"] = True
    STATE["phone_page_logged"] = False
    STATE["version"] = read_pack_version()
    STATE["last_error"] = ""

    print("================================================")
    print("  GROVELINK PHONE BRIDGE")
    print("  Version    :", STATE["version"])
    print("================================================")
    print("GTA folder :", gta_dir or "(not found — edit config.ini)")
    print("link.ini   :", ini)
    if galleries:
        print("Galleries  :")
        for g in galleries:
            print("   ", g)
    else:
        print("Galleries  : NONE YET (will re-check every second)")
        print("             Expected under Documents\\...\\Gallery")
    print("")
    print("  On your REAL PHONE open:")
    print("      http://%s:%s" % (ip, port))
    print("  On this PC you can also try:")
    print("      http://127.0.0.1:%s" % port)
    print("  Health JSON:")
    print("      http://127.0.0.1:%s/health" % port)
    print("  Share URL page (tap-to-copy, no QR lib):")
    print("      http://127.0.0.1:%s/qr" % port)
    print("  Max bridge photos (prune oldest):", max_photos)
    print("  Phone page poll_ms             :", poll_ms)
    print("  Export zip:")
    print("      http://127.0.0.1:%s/export.zip" % port)
    print("")
    print("  Keep this window open while you play.")
    print("================================================")
    sys.stdout.flush()

    write_open_on_phone(ip, port)
    write_ini_kv(ini, "STATUS", {"bridge": "1", "ip": ip})
    copy_latest(galleries)

    if cfg_flag(cfg, "server", "open_browser", True):
        local_url = "http://127.0.0.1:%s" % port
        # Defer slightly so the server socket is listening
        def _open():
            time.sleep(0.6)
            if try_open_browser(local_url):
                print("Opened browser:", local_url)
            else:
                print("Browser open skipped/failed (set server.open_browser=0 to silence)")

        bt = threading.Thread(target=_open)
        bt.daemon = True
        bt.start()

    t = threading.Thread(target=watcher, args=(cfg, gta_dir, ini))
    t.daemon = True
    t.start()

    server = HTTPServer(("0.0.0.0", port), Handler)
    server.link_ini = ini
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")
        try:
            write_ini_kv(ini, "STATUS", {"bridge": "0"})
        except Exception:
            pass


if __name__ == "__main__":
    main()
