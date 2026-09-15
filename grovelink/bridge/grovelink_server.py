# GroveLink bridge - Windows 7, Python 2.7 or 3.4-3.8, stdlib only
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
# 1.8.0 paths (also defined in helpers; keep early aliases for smoke overrides)
WEB_NEWS = os.path.join(HERE, "news")
CAPTIONS_PATH = os.path.join(HERE, "photos_captions.json")
CHAT_LOG_PATH = os.path.join(HERE, "chat_delivered.json")
FAVORITES_PATH = os.path.join(HERE, "photos_favorites.json")
COMMENTS_PATH = os.path.join(HERE, "photos_comments.json")
STREAK_PATH = os.path.join(HERE, "photos_streak.json")
REQUESTS_PATH = os.path.join(HERE, "requests.json")
POLL_PATH = os.path.join(HERE, "poll.json")


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
    "link_ini": "",
    "spectate_on": False,
    # IP -> last_seen unix for /spectate + /api/spectate polls (~30s window)
    "spectate_viewers": {},
    "started_at": 0,  # unix - set in main(); bridge uptime
    "pinned_chat_id": "",  # one pinned chat message id (empty = none)
    # 2.4.0 interactive
    "active_viewers": {},  # nick -> {nick, ip, last_seen}
    "rate_limit_send": {},  # ip -> last send unix
    "poll": None,  # mirror of poll.json when loaded
}

SPECTATE_VIEWER_WINDOW = 30


# --- 2.4.0 interactive: viewers, rate limit, requests, polls, broadcast ---


VIEWER_ACTIVE_WINDOW = 120  # names recently active (send/spectate/react) last 2 min
SEND_RATE_LIMIT_SEC = 3.0
ALLOWED_REQUEST_KINDS = ("camera", "news", "say_hi", "spectate_on")
REQUEST_KIND_LABELS = {
    "camera": "Take a Camera pic",
    "news": "Do a NEWS snap",
    "say_hi": "Say hi",
    "spectate_on": "Spectate on",
}


def _client_ip_from_handler(handler):
    try:
        return (handler.client_address[0] if handler.client_address else "") or ""
    except Exception:
        return ""


def note_active_viewer(nick, ip=""):
    """Track nickname activity for viewer list (last 2 min). Empty nick = prune only."""
    now = time.time()
    viewers = STATE.get("active_viewers")
    if not isinstance(viewers, dict):
        viewers = {}
    nick = (nick or "").strip()[:40]
    ip = (ip or "").strip()
    if nick:
        viewers[nick] = {"nick": nick, "ip": ip, "last_seen": now}
    cutoff = now - VIEWER_ACTIVE_WINDOW
    pruned = {}
    for k, v in viewers.items():
        try:
            if isinstance(v, dict) and float(v.get("last_seen") or 0) >= cutoff:
                pruned[k] = v
            elif not isinstance(v, dict) and float(v or 0) >= cutoff:
                pruned[k] = {"nick": k, "ip": "", "last_seen": float(v)}
        except Exception:
            pass
    STATE["active_viewers"] = pruned
    return pruned


def list_active_viewers():
    note_active_viewer("", "")
    viewers = STATE.get("active_viewers") or {}
    now = time.time()
    out = []
    for k, v in viewers.items():
        if not isinstance(v, dict):
            continue
        ts = float(v.get("last_seen") or 0)
        out.append({
            "nick": (v.get("nick") or k)[:40],
            "last_seen": int(ts),
            "ago_sec": int(max(0, now - ts)),
        })
    out.sort(key=lambda r: -r.get("last_seen", 0))
    return out[:40]


def check_send_rate_limit(ip):
    """Return (ok, wait_sec). 1 msg / SEND_RATE_LIMIT_SEC per IP."""
    ip = (ip or "").strip() or "unknown"
    now = time.time()
    bucket = STATE.get("rate_limit_send")
    if not isinstance(bucket, dict):
        bucket = {}
    # prune old
    cutoff = now - 60
    bucket = dict((k, v) for k, v in bucket.items() if float(v or 0) >= cutoff)
    last = float(bucket.get(ip) or 0)
    wait = SEND_RATE_LIMIT_SEC - (now - last)
    if last > 0 and wait > 0:
        STATE["rate_limit_send"] = bucket
        return False, max(0.1, round(wait, 1))
    bucket[ip] = now
    STATE["rate_limit_send"] = bucket
    return True, 0


def load_requests():
    data = _load_json_file(REQUESTS_PATH, [])
    if not isinstance(data, list):
        return []
    out = []
    for row in data[:80]:
        if isinstance(row, dict):
            out.append(row)
    return out


def save_requests(rows):
    _save_json_file(REQUESTS_PATH, (rows or [])[:80])


def _new_request_id():
    try:
        t = int(time.time() * 1000)
    except Exception:
        t = int(time.time())
    return "r%d" % t


def enqueue_request(kind, frm, ip=""):
    """Viewer request → requests.json + REQUEST.* in link.ini for CLEO toast."""
    kind = (kind or "").strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "cam": "camera", "photo": "camera", "pic": "camera", "camera_pic": "camera",
        "take_a_camera_pic": "camera",
        "herald": "news", "news_snap": "news", "do_a_news_snap": "news",
        "hi": "say_hi", "hello": "say_hi", "sayhi": "say_hi",
        "spectate": "spectate_on", "spec": "spectate_on", "spectateon": "spectate_on",
    }
    if kind in aliases:
        kind = aliases[kind]
    if kind not in ALLOWED_REQUEST_KINDS:
        return False, None, "bad kind (camera/news/say_hi/spectate_on)"
    frm = (frm or "Viewer").strip().replace("\r", " ").replace("\n", " ")[:40] or "Viewer"
    entry = {
        "id": _new_request_id(),
        "kind": kind,
        "label": REQUEST_KIND_LABELS.get(kind, kind),
        "from": frm,
        "ts": int(time.time()),
        "when": human_time(time.time()),
        "status": "pending",
        "ip": (ip or "")[:40],
    }
    rows = load_requests()
    rows.insert(0, entry)
    save_requests(rows[:80])
    note_active_viewer(frm, ip)
    # Write CLEO toast flag
    ini = STATE.get("link_ini") or ""
    if ini:
        try:
            label = REQUEST_KIND_LABELS.get(kind, kind)
            text = ("%s from %s" % (label, frm)).replace("=", "-")[:60]
            write_ini_kv(ini, "REQUEST", {
                "new": "1",
                "kind": kind.replace("=", "-")[:40],
                "from": frm.replace("=", "-")[:40],
                "text": text,
            })
        except Exception as exc:
            print("REQUEST ini error:", exc)
    return True, entry, "queued"


def mark_request_done(req_id, clear_all=False):
    rows = load_requests()
    if clear_all:
        for r in rows:
            if isinstance(r, dict) and r.get("status") == "pending":
                r["status"] = "done"
        save_requests(rows)
        return True, "cleared"
    req_id = (req_id or "").strip()
    if not req_id:
        return False, "missing id"
    hit = False
    for r in rows:
        if isinstance(r, dict) and str(r.get("id") or "") == req_id:
            r["status"] = "done"
            hit = True
            break
    if not hit:
        return False, "not found"
    save_requests(rows)
    return True, "done"


def pending_requests():
    return [r for r in load_requests() if isinstance(r, dict) and r.get("status") == "pending"]


def load_poll():
    data = _load_json_file(POLL_PATH, None)
    if isinstance(data, dict) and data.get("id"):
        return data
    return None


def save_poll(poll):
    if poll is None:
        try:
            if os.path.isfile(POLL_PATH):
                os.remove(POLL_PATH)
        except Exception:
            pass
        return
    _save_json_file(POLL_PATH, poll)


def _new_poll_id():
    try:
        t = int(time.time() * 1000)
    except Exception:
        t = int(time.time())
    return "p%d" % t


def create_poll(question, options, frm="Host"):
    question = (question or "").strip().replace("\r", " ").replace("\n", " ")[:120]
    if not question:
        return False, None, "missing question"
    opts = []
    if isinstance(options, (list, tuple)):
        raw_opts = options
    else:
        raw_opts = str(options or "").split("|")
    for o in raw_opts:
        o = (o or "").strip().replace("\r", " ").replace("\n", " ")[:40]
        if o:
            opts.append(o)
    opts = opts[:4]
    if len(opts) < 2:
        return False, None, "need 2-4 options"
    poll = {
        "id": _new_poll_id(),
        "question": question,
        "options": opts,
        "votes": dict((str(i), 0) for i in range(len(opts))),
        "voters": {},
        "open": True,
        "ts": int(time.time()),
        "when": human_time(time.time()),
        "from": (frm or "Host")[:40],
    }
    save_poll(poll)
    STATE["poll"] = poll
    # CLEO toast
    ini = STATE.get("link_ini") or ""
    if ini:
        try:
            write_ini_kv(ini, "POLL", {
                "new": "1",
                "question": question.replace("=", "-")[:60],
                "summary": "",
            })
        except Exception as exc:
            print("POLL ini error:", exc)
    return True, poll, "created"


def vote_poll(option_idx, ip="", nick=""):
    poll = load_poll()
    if not poll or not poll.get("open"):
        return False, None, "no open poll"
    try:
        idx = int(option_idx)
    except Exception:
        return False, None, "bad option"
    opts = poll.get("options") or []
    if idx < 0 or idx >= len(opts):
        return False, None, "bad option"
    ip = (ip or "").strip() or "anon"
    voters = poll.get("voters")
    if not isinstance(voters, dict):
        voters = {}
    if ip in voters:
        return False, poll, "already voted"
    votes = poll.get("votes")
    if not isinstance(votes, dict):
        votes = dict((str(i), 0) for i in range(len(opts)))
    key = str(idx)
    votes[key] = int(votes.get(key) or 0) + 1
    voters[ip] = idx
    poll["votes"] = votes
    poll["voters"] = voters
    save_poll(poll)
    STATE["poll"] = poll
    if nick:
        note_active_viewer(nick, ip)
    return True, poll, "voted"


def close_poll(write_inbox=True):
    poll = load_poll()
    if not poll:
        return False, None, "no poll"
    poll["open"] = False
    opts = poll.get("options") or []
    votes = poll.get("votes") or {}
    parts = []
    for i, o in enumerate(opts):
        n = int(votes.get(str(i)) or 0)
        parts.append("%s %d" % ((o or ("#%d" % i))[:20], n))
    summary = "Poll done: " + " ".join(parts)
    summary = summary[:80]
    poll["summary"] = summary
    save_poll(poll)
    STATE["poll"] = poll
    ini = STATE.get("link_ini") or ""
    if ini:
        try:
            write_ini_kv(ini, "POLL", {
                "new": "0",
                "summary": summary.replace("=", "-")[:80],
            })
            if write_inbox:
                write_ini_kv(ini, "INBOX", {
                    "new": "1",
                    "from": "POLL",
                    "msg": summary.replace("=", "-")[:80],
                })
        except Exception as exc:
            print("close poll ini error:", exc)
    return True, poll, summary


def poll_payload(poll=None):
    poll = poll if poll is not None else load_poll()
    if not poll:
        return None
    opts = poll.get("options") or []
    votes = poll.get("votes") or {}
    tallies = []
    total = 0
    for i, o in enumerate(opts):
        n = int(votes.get(str(i)) or 0)
        total += n
        tallies.append({"index": i, "label": o, "votes": n})
    return {
        "id": poll.get("id"),
        "question": poll.get("question"),
        "options": opts,
        "tallies": tallies,
        "total": total,
        "open": bool(poll.get("open")),
        "summary": poll.get("summary") or "",
        "when": poll.get("when") or "",
        "from": poll.get("from") or "",
        "voter_count": len(poll.get("voters") or {}),
    }


def append_chat_broadcast(frm, msg):
    """System/CJ broadcast to all viewers (chat log + /api)."""
    log = load_chat_log()
    entry = _ensure_chat_entry_shape({
        "id": _new_chat_id(),
        "from": (frm or "CJ")[:40],
        "msg": (msg or "")[:80],
        "ts": int(time.time()),
        "when": human_time(time.time()),
        "delivered": False,
        "role": "cj",
        "side": "cj",
        "broadcast": True,
        "system": True,
        "reactions": dict((k, 0) for k in ALLOWED_REACTIONS),
    })
    log.insert(0, entry)
    log = log[:40]
    _save_json_file(CHAT_LOG_PATH, log)
    STATE["inbox"] = log
    return entry


def do_broadcast(msg, frm="CJ"):
    msg = (msg or "").strip().replace("\r", " ").replace("\n", " ")[:80]
    frm = (frm or "CJ").strip().replace("\r", " ").replace("\n", " ")[:40] or "CJ"
    if not msg:
        return False, None, "empty message"
    entry = append_chat_broadcast(frm, msg)
    return True, entry, "broadcast"


def process_poll_section(ini):
    """If CLEO writes POLL.create=1 with question/options, create poll."""
    if not ini or not os.path.isfile(ini):
        return False
    create = read_ini_key(ini, "POLL", "create", "0")
    if create != "1":
        return False
    q = read_ini_key(ini, "POLL", "question", "")
    opts_raw = read_ini_key(ini, "POLL", "options", "")
    write_ini_kv(ini, "POLL", {"create": "0"})
    opts = [o.strip() for o in (opts_raw or "").split("|") if o.strip()]
    ok, poll, detail = create_poll(q, opts, frm="CJ")
    if ok:
        print("CLEO poll created:", (poll.get("question") or "")[:50])
    else:
        print("CLEO poll failed:", detail)
    return ok


def process_outbox_broadcast(ini):
    """OUTBOX with to=ALL → broadcast without duplicating normal CJ reply path.
    Called from process_outbox_flag when to=ALL."""
    pass  # handled inside process_outbox_flag




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
    """True for paths like C:\\... - skip creating those on non-Windows."""
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
    _mkdir(WEB_NEWS)
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
                    "[OUTBOX]\nnew=0\nfrom=CJ\nmsg=\n\n"
                    "[STATUS]\nbridge=1\nip=0.0.0.0\nwanted=0\nmoney=0\nzone=\nhour=-1\nspectate=0\n\n"
                    "[NEWS]\nnew=0\nmake=0\nzone=\n\n"
                    "[SPECTATE]\non=0\nframe=0\n"
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
    try:
        kept = attach_captions_to_photos(kept)
    except Exception:
        pass
    try:
        kept = attach_comments_to_photos(kept)
    except Exception:
        pass
    try:
        note_streak_from_photos(kept)
    except Exception:
        pass
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
        "GroveLink - open on your phone (same Wi-Fi as this PC)\n"
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
                os.startfile(url)  # noqa: PTH118 - Win7 bridge
                return True
            except Exception:
                pass
        if webbrowser is not None:
            webbrowser.open(url)
            return True
    except Exception as exc:
        print("Could not open browser:", exc)
    return False


# --- GroveLink 1.8.0: captions, Breaking News, chat helpers (injected) ---

WEB_NEWS = os.path.join(HERE, "news")
# CAPTIONS_PATH / CHAT_LOG_PATH already set near top (smoke may override early aliases)
CAPTIONS_PATH = os.path.join(HERE, "photos_captions.json")
CHAT_LOG_PATH = os.path.join(HERE, "chat_delivered.json")

# Keyword pools for satirical SA-style headlines (offline, no AI)
_NEWS_PLACES = (
    "Grove Street", "Ganton", "Idlewood", "Los Santos", "San Andreas",
    "East Beach", "Vinewood", "Verdant Meadows", "Area 69", "Mount Chiliad",
    "Angel Pine", "Las Venturas", "San Fierro", "Flint County", "Red County",
)
_NEWS_VERBS = (
    "Spotted", "Caught", "Seen", "Photographed", "Reported", "Witnessed",
    "Tracked", "Busted", "Hailed", "Exposed",
)
_NEWS_SUBJECTS = (
    "local hero", "mystery rider", "Grove soldier", "street legend",
    "camera-happy civilian", "unidentified Ballas lookout", "CJ lookalike",
    "tourist with a phone", "hood paparazzo", "midnight wanderer",
)
_NEWS_ANGLES = (
    "sources say the shot was pure San Andreas chaos",
    "neighbors claim the flash scared the cats off the roof",
    "SPD declined to comment, citing 'ongoing vibes'",
    "Sweet reportedly muttered 'stay Grove' under his breath",
    "Ryder insists he was 'just checking the scenery'",
    "weather desk notes clear skies and questionable decisions",
    "editors remind readers: this is satire, not a wanted poster",
    "byline desk filed this under BREAKING / probably fine",
)
_NEWS_WEATHER = (
    "Sunny with a chance of drive-bys (figuratively)",
    "Low smog, high drama",
    "Partly cloudy over Grove; Ballas outlook: unsettled",
    "Heat advisory for anyone standing near a camera flash",
    "Clear skies; keep your phone charged, CJ",
    "Evening haze over Idlewood; flash recommended",
    "Fog rolling off the docks - mind the camera lens",
)
_NEWS_DESKS = (
    "City Desk", "Crime & Vibes Desk", "Photo Desk", "Neighborhood Desk",
    "Culture Desk", "Night Beat", "Grove Bureau",
)
_NEWS_PULLS = (
    '"It was pure San Andreas," one neighbor insisted, waving a phone.',
    '"Stay Grove," muttered a voice from a porch across the street.',
    '"SPD had no comment - only vibes," the desk noted dryly.',
    '"That flash scared the cats off the roof," witnesses claimed.',
    '"Not a wanted poster - satire only," editors remind readers.',
    '"Keep the bridge window open," a helpful civilian texted CJ.',
)
_NEWS_RELATED = (
    "Related: Camera != Breaking News - gallery snaps stay on the phone page.",
    "Related: File location tags via NEWS menu or the web Breaking News dialog.",
    "Related: LIVE SPECTATE is snapshot slideshow, not H.264 video.",
    "Related: Text CJ from the sticky composer; he replies via REPLY in-game.",
    "Related: Session recap counts today's photos, news, and chat.",
)
_NEWS_COLOR = (
    "A bystander claimed the still looked expensive, which in Los Santos means someone almost crashed.",
    "Local cats resumed rooftop patrol within minutes; editorial confidence remains high.",
    "The Herald's fact-check unit (one intern, one clipboard) stamped this SATIRE / PROBABLY FINE.",
    "Traffic briefly slowed as drivers rubbernecked at someone holding a real phone in 1992.",
    "Smoke allegedly asked if the photo would make the Herald. It did. You're reading it.",
)

# Map common SA info-zone GXT keys (0843, max 8 chars) → Herald-friendly tags
_ZONE_FRIENDLY = {
    "GAN1": "Grove Street", "GAN2": "Ganton", "LAE": "East Los Santos",
    "LAE2": "East Beach", "LAES": "Los Santos", "IDLE": "Idlewood",
    "JEFF": "Jefferson", "GLN1": "Glen Park", "GLN2": "Glen Park",
    "LMEX": "Little Mexico", "LIND": "Los Santos", "COM": "Commerce",
    "IWD": "Idlewood", "ELS": "El Corona", "LDOC": "Ocean Docks",
    "LSX": "LS Airport", "VEG": "Las Venturas", "VEGA": "Las Venturas",
    "VEGE": "Las Venturas", "VEGS": "Las Venturas", "ROCE": "Rodeo",
    "SUN1": "Santa Maria Beach", "SUN2": "Santa Maria Beach",
    "VIN1": "Vinewood", "VIN2": "Vinewood", "VIN3": "Vinewood",
    "SMB": "Santa Maria Beach", "MAR": "Marina", "LDT": "Downtown LS",
    "LDS": "Los Santos", "BLUF": "Verdant Bluffs", "CHC": "Chinatown",
    "SUNA": "San Fierro", "SFA": "San Fierro", "SFN": "San Fierro",
    "SFE": "San Fierro", "SFW": "San Fierro", "SFS": "San Fierro",
    "HYA": "Hunter Quarry", "BONE": "Bone County", "RED": "Red County",
    "FLINT": "Flint County", "WHET": "Whetstone", "ANGP": "Angel Pine",
    "MTCH": "Mount Chiliad", "AREA": "Area 69", "VERO": "Verdant Meadows",
}


def normalize_location(loc):
    """Sanitize optional location tag from CLEO NEWS.zone / web POST."""
    if loc is None:
        return ""
    s = str(loc).strip().replace("\r", " ").replace("\n", " ")
    s = s.replace("=", "-")[:48]
    if not s:
        return ""
    key = s.upper().replace(" ", "")
    if key in _ZONE_FRIENDLY:
        return _ZONE_FRIENDLY[key]
    # Already a friendly place (spaces / long enough)
    return s


def _safe_basename(name):
    name = os.path.basename(name or "")
    if not name or name in (".", "..") or ".." in name or "/" in name or "\\" in name:
        return ""
    return name


def _load_json_file(path, default):
    if not os.path.isfile(path):
        return default
    try:
        with open(path, "r") as f:
            raw = f.read()
        if not raw.strip():
            return default
        obj = json.loads(raw)
        return obj if obj is not None else default
    except Exception:
        return default


def _save_json_file(path, obj):
    try:
        _mkdir(os.path.dirname(path) or HERE)
        tmp = path + ".tmp"
        with open(tmp, "w") as f:
            f.write(json.dumps(obj, indent=2, sort_keys=True))
            f.write("\n")
        try:
            if os.path.isfile(path):
                os.remove(path)
        except Exception:
            pass
        os.rename(tmp, path)
        return True
    except Exception as exc:
        try:
            with open(path, "w") as f:
                f.write(json.dumps(obj))
            return True
        except Exception as exc2:
            print("Could not save JSON", path, exc2)
            return False


def load_captions():
    data = _load_json_file(CAPTIONS_PATH, {})
    if not isinstance(data, dict):
        return {}
    return data


def save_captions(data):
    return _save_json_file(CAPTIONS_PATH, data if isinstance(data, dict) else {})


def get_caption(name):
    name = _safe_basename(name)
    if not name:
        return ""
    caps = load_captions()
    val = caps.get(name) or ""
    # Sidecar .txt fallback
    if not val:
        side = os.path.join(WEB_PHOTOS, name + ".txt")
        if os.path.isfile(side):
            try:
                with open(side, "r") as f:
                    val = f.read().strip()[:200]
            except Exception:
                val = ""
    return val


def set_caption(name, caption):
    name = _safe_basename(name)
    if not name:
        return False, "bad name"
    caption = (caption or "").strip().replace("\r", " ").replace("\n", " ")[:200]
    caps = load_captions()
    if caption:
        caps[name] = caption
        # Also write sidecar .txt for easy browsing on disk
        try:
            side = os.path.join(WEB_PHOTOS, name + ".txt")
            with open(side, "w") as f:
                f.write(caption + "\n")
        except Exception:
            pass
    else:
        if name in caps:
            del caps[name]
        try:
            side = os.path.join(WEB_PHOTOS, name + ".txt")
            if os.path.isfile(side):
                os.remove(side)
        except Exception:
            pass
    save_captions(caps)
    return True, caption




# --- 2.3.0 photo comments + photo-day streak ---

def load_comments():
    data = _load_json_file(COMMENTS_PATH, {})
    if not isinstance(data, dict):
        return {}
    return data


def save_comments(data):
    return _save_json_file(COMMENTS_PATH, data if isinstance(data, dict) else {})


def get_comment(name):
    name = _safe_basename(name)
    if not name:
        return ""
    comments = load_comments()
    val = comments.get(name) or ""
    if not val:
        side = os.path.join(WEB_PHOTOS, name + ".comment.txt")
        if os.path.isfile(side):
            try:
                with open(side, "r") as f:
                    val = f.read().strip()[:140]
            except Exception:
                val = ""
    return val


def set_comment(name, comment):
    """Short text comment on a photo (beside captions JSON + sidecar)."""
    name = _safe_basename(name)
    if not name:
        return False, "bad name"
    comment = (comment or "").strip().replace("\r", " ").replace("\n", " ")[:140]
    comments = load_comments()
    if comment:
        comments[name] = comment
        try:
            side = os.path.join(WEB_PHOTOS, name + ".comment.txt")
            with open(side, "w") as f:
                f.write(comment + "\n")
        except Exception:
            pass
    else:
        if name in comments:
            del comments[name]
        try:
            side = os.path.join(WEB_PHOTOS, name + ".comment.txt")
            if os.path.isfile(side):
                os.remove(side)
        except Exception:
            pass
    save_comments(comments)
    return True, comment


def attach_comments_to_photos(photos):
    comments = load_comments()
    out = []
    for p in photos or []:
        if not isinstance(p, dict):
            out.append(p)
            continue
        item = dict(p)
        name = item.get("file") or ""
        c = comments.get(name) or ""
        if not c and name:
            side = os.path.join(WEB_PHOTOS, name + ".comment.txt")
            if os.path.isfile(side):
                try:
                    with open(side, "r") as f:
                        c = f.read().strip()[:140]
                except Exception:
                    c = ""
        item["comment"] = c
        out.append(item)
    return out


def _ymd_from_ts(ts):
    try:
        return time.strftime("%Y-%m-%d", time.localtime(int(ts)))
    except Exception:
        return ""


def load_streak_dates():
    data = _load_json_file(STREAK_PATH, {"dates": []})
    dates = []
    if isinstance(data, dict):
        raw = data.get("dates") or []
    elif isinstance(data, list):
        raw = data
    else:
        raw = []
    for d in raw:
        s = str(d or "").strip()
        if len(s) == 10 and s[4] == "-" and s[7] == "-":
            dates.append(s)
    return sorted(set(dates))


def save_streak_dates(dates):
    cleaned = sorted(set(str(d).strip() for d in (dates or []) if str(d).strip()))
    return _save_json_file(STREAK_PATH, {"dates": cleaned})


def note_streak_from_photos(photos):
    """Merge YYYY-MM-DD of photo mtimes into streak date set (days with >=1 photo)."""
    dates = set(load_streak_dates())
    for p in photos or []:
        if not isinstance(p, dict):
            continue
        ymd = _ymd_from_ts(p.get("mtime") or 0)
        if ymd:
            dates.add(ymd)
    # Always note today if any photo is from today
    today0 = _start_of_today_sec()
    for p in photos or []:
        if not isinstance(p, dict):
            continue
        try:
            if int(p.get("mtime") or 0) >= today0:
                dates.add(_ymd_from_ts(time.time()))
                break
        except Exception:
            pass
    save_streak_dates(dates)
    return sorted(dates)


def compute_streak(dates=None):
    """Consecutive days with >=1 photo ending today (0 if today missing)."""
    if dates is None:
        dates = load_streak_dates()
    dset = set(dates or [])
    if not dset:
        return 0
    try:
        cur = time.strftime("%Y-%m-%d", time.localtime())
    except Exception:
        return 0
    if cur not in dset:
        return 0
    n = 0
    y, m, d = [int(x) for x in cur.split("-")]
    import datetime as _dt
    day = _dt.date(y, m, d)
    while day.strftime("%Y-%m-%d") in dset:
        n += 1
        day = day - _dt.timedelta(days=1)
    return n


def streak_payload():
    dates = load_streak_dates()
    return {
        "streak": compute_streak(dates),
        "photo_days": len(dates),
        "dates": dates[-60:],  # cap for /api
    }


ALLOWED_REACTIONS = ("👍", "😂", "🔥")  # thumbs / laugh / fire


def _new_chat_id():
    """Stable-enough id for chat log entries (reactions / pin)."""
    try:
        t = int(time.time() * 1000)
    except Exception:
        t = int(time.time())
    return "c%d" % t


def _ensure_chat_entry_shape(entry, idx=0):
    """Backfill id + reactions on older chat log rows."""
    if not isinstance(entry, dict):
        return entry
    if not entry.get("id"):
        ts = entry.get("ts") or 0
        try:
            entry["id"] = "c%d_%d" % (int(ts), int(idx))
        except Exception:
            entry["id"] = _new_chat_id()
    react = entry.get("reactions")
    if not isinstance(react, dict):
        react = {}
    for key in ALLOWED_REACTIONS:
        if key not in react:
            react[key] = 0
        else:
            try:
                react[key] = max(0, int(react[key]))
            except Exception:
                react[key] = 0
    entry["reactions"] = react
    return entry


def load_chat_log():
    data = _load_json_file(CHAT_LOG_PATH, [])
    if not isinstance(data, list):
        return []
    out = []
    for i, row in enumerate(data[:50]):
        if isinstance(row, dict):
            out.append(_ensure_chat_entry_shape(dict(row), i))
    return out


def append_chat_delivered(frm, msg):
    log = load_chat_log()
    entry = _ensure_chat_entry_shape({
        "id": _new_chat_id(),
        "from": (frm or "REAL PHONE")[:40],
        "msg": (msg or "")[:80],
        "ts": int(time.time()),
        "when": human_time(time.time()),
        "delivered": True,
        "role": "visitor",
        "side": "visitor",
        "reactions": dict((k, 0) for k in ALLOWED_REACTIONS),
    })
    log.insert(0, entry)
    log = log[:40]
    _save_json_file(CHAT_LOG_PATH, log)
    STATE["inbox"] = log
    return entry


def append_chat_cj_reply(frm, msg):
    """CJ reply from CLEO OUTBOX - show as CJ bubble on web thread."""
    log = load_chat_log()
    entry = _ensure_chat_entry_shape({
        "id": _new_chat_id(),
        "from": (frm or "CJ")[:40],
        "msg": (msg or "")[:80],
        "ts": int(time.time()),
        "when": human_time(time.time()),
        "delivered": False,
        "role": "cj",
        "side": "cj",
        "reactions": dict((k, 0) for k in ALLOWED_REACTIONS),
    })
    log.insert(0, entry)
    log = log[:40]
    _save_json_file(CHAT_LOG_PATH, log)
    STATE["inbox"] = log
    return entry


def find_chat_entry(msg_id):
    msg_id = (msg_id or "").strip()
    if not msg_id:
        return None
    for row in load_chat_log():
        if isinstance(row, dict) and str(row.get("id") or "") == msg_id:
            return row
    return None


def react_to_chat(msg_id, emoji):
    """Increment a reaction count on a chat message. Returns (ok, entry|detail)."""
    emoji = (emoji or "").strip()
    # Accept short aliases
    aliases = {
        "up": "👍", "thumb": "👍", "thumbsup": "👍", "+1": "👍",
        "laugh": "😂", "lol": "😂", "joy": "😂",
        "fire": "🔥", "hot": "🔥",
        "thumbs_up": "👍",
    }
    if emoji in aliases:
        emoji = aliases[emoji]
    # Also map literal escaped forms if callers send unicode
    if emoji not in ALLOWED_REACTIONS:
        return False, "bad reaction"
    msg_id = (msg_id or "").strip()
    if not msg_id:
        return False, "missing id"
    log = load_chat_log()
    hit = None
    for i, row in enumerate(log):
        if isinstance(row, dict) and str(row.get("id") or "") == msg_id:
            row = _ensure_chat_entry_shape(row, i)
            row["reactions"][emoji] = int(row["reactions"].get(emoji) or 0) + 1
            log[i] = row
            hit = row
            break
    if not hit:
        return False, "not found"
    _save_json_file(CHAT_LOG_PATH, log[:40])
    STATE["inbox"] = log[:40]
    return True, hit


def pin_chat_message(msg_id):
    """Pin one chat message (empty id clears). Stored in STATE; exposed via /api."""
    msg_id = (msg_id or "").strip()
    if not msg_id:
        STATE["pinned_chat_id"] = ""
        return True, None, "unpinned"
    entry = find_chat_entry(msg_id)
    if not entry:
        return False, None, "not found"
    STATE["pinned_chat_id"] = str(entry.get("id") or msg_id)
    return True, entry, "pinned"


def get_pinned_chat():
    pid = (STATE.get("pinned_chat_id") or "").strip()
    if not pid:
        return None
    return find_chat_entry(pid)


def bridge_uptime_sec():
    started = int(STATE.get("started_at") or 0)
    if started <= 0:
        return 0
    try:
        return max(0, int(time.time()) - started)
    except Exception:
        return 0


def format_uptime(sec):
    sec = max(0, int(sec or 0))
    h = sec // 3600
    m = (sec % 3600) // 60
    s = sec % 60
    if h > 0:
        return "%dh %dm" % (h, m)
    if m > 0:
        return "%dm %ds" % (m, s)
    return "%ds" % s


def _start_of_today_sec():
    try:
        lt = time.localtime()
        return int(time.mktime((lt.tm_year, lt.tm_mon, lt.tm_mday, 0, 0, 0, 0, 0, -1)))
    except Exception:
        return int(time.time()) - 86400


def session_recap_data():
    """Today's photo / news / chat counts + top location (stdlib)."""
    today0 = _start_of_today_sec()
    photos = STATE.get("photos") or []
    try:
        photos = attach_locations_to_photos(photos)
    except Exception:
        pass
    photo_n = 0
    for p in photos:
        if not isinstance(p, dict):
            continue
        try:
            if int(p.get("mtime") or 0) >= today0:
                photo_n += 1
        except Exception:
            pass
    news_n = 0
    for art in list_news_articles(80):
        try:
            if int(art.get("mtime") or 0) >= today0:
                news_n += 1
        except Exception:
            pass
    chat_n = 0
    for row in load_chat_log():
        if not isinstance(row, dict):
            continue
        try:
            if int(row.get("ts") or 0) >= today0:
                chat_n += 1
        except Exception:
            pass
    places = places_summary(photos)
    top_place = ""
    top_count = 0
    if places:
        top_place = places[0].get("place") or ""
        top_count = int(places[0].get("count") or 0)
    try:
        note_streak_from_photos(photos)
    except Exception:
        pass
    streak = streak_payload()
    return {
        "ok": True,
        "photo_count_today": photo_n,
        "news_count_today": news_n,
        "chat_count_today": chat_n,
        "top_location": top_place,
        "top_location_count": top_count,
        "uptime_sec": bridge_uptime_sec(),
        "uptime_human": format_uptime(bridge_uptime_sec()),
        "version": STATE.get("version", "unknown") or "unknown",
        "streak": streak.get("streak", 0),
        "photo_days": streak.get("photo_days", 0),
        "streak_dates": streak.get("dates") or [],
    }



def process_outbox_flag(ini):
    """When OUTBOX.new=1, clear flag and append CJ reply (or broadcast if to=ALL)."""
    if not ini or not os.path.isfile(ini):
        return False
    new = read_ini_key(ini, "OUTBOX", "new", "0")
    if new != "1":
        return False
    msg = read_ini_key(ini, "OUTBOX", "msg", "")
    frm = read_ini_key(ini, "OUTBOX", "from", "CJ") or "CJ"
    to = (read_ini_key(ini, "OUTBOX", "to", "") or "").strip().upper()
    write_ini_kv(ini, "OUTBOX", {"new": "0", "to": ""})
    try:
        if to in ("ALL", "*", "BROADCAST"):
            entry = append_chat_broadcast(frm, msg)
            print("CJ broadcast → chat:", (entry.get("msg") or "")[:60])
        else:
            entry = append_chat_cj_reply(frm, msg)
            print("CJ reply → chat:", (entry.get("msg") or "")[:60])
    except Exception as exc:
        print("OUTBOX error:", exc)
    return True


def _pick(seq, seed):
    if not seq:
        return ""
    try:
        idx = abs(int(seed)) % len(seq)
    except Exception:
        idx = 0
    return seq[idx]


def _keywords_from_photo(photo_name, mtime=0):
    """Derive light keywords from filename + time (stdlib only)."""
    name = _safe_basename(photo_name) or "shot"
    base = name.rsplit(".", 1)[0]
    bits = []
    for part in base.replace("-", "_").split("_"):
        part = part.strip()
        if not part:
            continue
        if part.isdigit() and len(part) >= 8:
            continue
        if len(part) >= 3:
            bits.append(part[:24])
    hour = 12
    try:
        hour = int(time.localtime(mtime or time.time()).tm_hour)
    except Exception:
        hour = 12
    if hour < 5:
        bits.append("late night")
    elif hour < 11:
        bits.append("morning")
    elif hour < 17:
        bits.append("afternoon")
    else:
        bits.append("evening")
    return bits[:6]


def generate_news_article(photo_name, caption="", auto=False, location=""):
    """Build satirical Grove Street Herald article - multi-graf, offline templates."""
    photo_name = _safe_basename(photo_name)
    if not photo_name:
        return None
    full = os.path.join(WEB_PHOTOS, photo_name)
    mtime = 0
    if os.path.isfile(full):
        try:
            mtime = int(os.path.getmtime(full))
        except Exception:
            mtime = int(time.time())
    else:
        mtime = int(time.time())
    if not caption:
        caption = get_caption(photo_name)
    location = normalize_location(location)
    kws = _keywords_from_photo(photo_name, mtime)
    seed = mtime ^ (len(photo_name) * 17) ^ (len(caption) * 31) ^ (len(location) * 13)
    place = location if location else _pick(_NEWS_PLACES, seed)
    verb = _pick(_NEWS_VERBS, seed // 3)
    subject = _pick(_NEWS_SUBJECTS, seed // 5)
    angle = _pick(_NEWS_ANGLES, seed // 7)
    weather = _pick(_NEWS_WEATHER, seed // 11)
    desk = _pick(_NEWS_DESKS, seed // 13)
    pull = _pick(_NEWS_PULLS, seed // 17)
    related = _pick(_NEWS_RELATED, seed // 19)
    color = _pick(_NEWS_COLOR, seed // 23)
    kw_bit = ""
    if kws:
        kw_bit = kws[0]
    if caption:
        frag = caption[:48]
        headline = "BREAKING: %s - %s near %s" % (verb, frag, place)
    elif kw_bit and not kw_bit.isdigit():
        headline = "BREAKING: %s %s %s near %s" % (verb, subject, kw_bit, place)
    else:
        headline = "BREAKING: %s %s near %s" % (verb, subject, place)
    headline = headline[:120]
    # Subhead (deck)
    if location:
        subhead = (
            "On-scene from %s: a %s was %s as the real-phone feed lit up GroveLink."
            % (location, subject, verb.lower())
        )
    else:
        subhead = (
            "Witnesses say a %s was %s near %s - details from the GroveLink still."
            % (subject, verb.lower(), place)
        )
    subhead = subhead[:160]
    byline = "By %s · Grove Street Herald" % desk
    stamp = human_time(mtime)
    filed = human_time(time.time())
    # Dateline
    try:
        lt = time.localtime(mtime or time.time())
        date_s = time.strftime("%A, %B %d, %Y", lt)
    except Exception:
        date_s = stamp
    dateline = "%s - %s" % (place.upper(), date_s)
    photo_credit = "Photo credit: GroveLink bridge still · /photo/%s" % photo_name

    body_parts = []
    # Graf 1 - lead
    body_parts.append(
        "%s In a development that surprised absolutely nobody along %s, "
        "a %s was %s with what witnesses describe as \"a very phone-looking phone.\" "
        "The Grove Street Herald obtained the still through the GroveLink companion bridge "
        "running on the same Wi-Fi as the game PC."
        % (dateline + ".", place, subject, verb.lower())
    )
    body_parts.append("")
    # Graf 2 - angle + weather
    body_parts.append(
        angle[0].upper() + angle[1:] + ". Weather desk adds: %s."
        % weather
    )
    body_parts.append("")
    # Graf 3 - location / caption / keywords
    if location:
        body_parts.append(
            "Location desk tagged this filing at %s after the CLEO NEWS snap "
            "(or the web Breaking News confirm). Camera snaps alone never file Herald copy - "
            "Camera stays gallery-only; NEWS is a separate menu."
            % location
        )
        body_parts.append("")
    if caption:
        body_parts.append(
            'On-scene caption from the real-phone feed: \"%s\"' % caption[:160]
        )
        body_parts.append("")
    if kws:
        body_parts.append(
            "Filename desk notes keywords: %s. Editors cross-checked against "
            "known San Andreas place names and time-of-day cues from the file mtime."
            % ", ".join(kws[:4])
        )
        body_parts.append("")
    # Graf 4 - color
    body_parts.append(color)
    body_parts.append("")
    # Graf 5 - how it works / disclaimer
    body_parts.append(
        "How this landed: a GroveLink bridge watcher burst-copied the Gallery still "
        "into bridge/photos, then the Herald generator assembled this satirical column "
        "from offline templates (no external AI APIs). Readers on the phone page can "
        "star, caption, comment, or share the same frame."
    )
    body_parts.append("")
    body_parts.append(
        "The Grove Street Herald reminds readers this column is satirical fan content "
        "for single-player San Andreas shenanigans - not real news, not a police blotter, "
        "and not affiliated with Rockstar Games."
    )
    body_parts.append("")
    body_parts.append(photo_credit + ".")
    if auto:
        body_parts.append("")
        body_parts.append(
            "(Legacy note: auto-draft path retained for older configs; "
            "1.8.1+ never auto-files on Camera shutter - NEWS.make or web POST /news only.)"
        )

    art_id = "n%d_%s" % (int(time.time()), abs(seed) % 100000)
    article = {
        "id": art_id,
        "headline": headline,
        "subhead": subhead,
        "byline": byline,
        "desk": desk,
        "dateline": dateline,
        "pull_quote": pull,
        "related": related,
        "photo_credit": photo_credit,
        "body": "\n".join(body_parts),
        "photo": photo_name,
        "caption": caption or "",
        "timestamp": stamp,
        "filed": filed,
        "mtime": mtime,
        "weather": weather,
        "place": place,
        "location": location,
        "auto": bool(auto),
        "keywords": kws,
    }
    return article


def save_news_article(article):
    if not article or not article.get("id"):
        return False, "bad article"
    _mkdir(WEB_NEWS)
    path = os.path.join(WEB_NEWS, article["id"] + ".json")
    if not _save_json_file(path, article):
        return False, "write failed"
    return True, article["id"]


def load_news_article(art_id):
    art_id = os.path.basename(art_id or "").replace("..", "")
    if not art_id:
        return None
    if not art_id.endswith(".json"):
        path = os.path.join(WEB_NEWS, art_id + ".json")
    else:
        path = os.path.join(WEB_NEWS, art_id)
        art_id = art_id[:-5]
    data = _load_json_file(path, None)
    if not isinstance(data, dict):
        return None
    if not data.get("id"):
        data["id"] = art_id
    return data


def list_news_articles(limit=40):
    _mkdir(WEB_NEWS)
    out = []
    try:
        names = os.listdir(WEB_NEWS)
    except Exception:
        return []
    for name in names:
        if not name.endswith(".json"):
            continue
        art = load_news_article(name[:-5])
        if art:
            out.append(art)
    out.sort(key=lambda a: int(a.get("mtime") or 0), reverse=True)
    return out[:limit]


def create_news_from_photo(photo_name, caption="", auto=False, link_ini=None, location=""):
    article = generate_news_article(
        photo_name, caption=caption, auto=auto, location=location
    )
    if not article:
        return False, None, "bad photo"
    ok, art_id = save_news_article(article)
    if not ok:
        return False, None, "save failed"
    # Optional CLEO toast flag
    if link_ini:
        try:
            write_ini_kv(link_ini, "NEWS", {"new": "1"})
        except Exception:
            pass
    return True, article, "ok"


def _esc(s):
    s = "" if s is None else str(s)
    return (
        s.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def render_news_index():
    arts = list_news_articles(40)
    rows = []
    if not arts:
        rows.append(
            '<div class="empty"><h2>No stories filed yet</h2>'
            "<p>Open the phone page, pick a shot, tap <b>Breaking News</b> "
            "(or use CLEO <b>NEWS</b> - Camera alone never files Herald).</p></div>"
        )
    for a in arts:
        aid = _esc(a.get("id") or "")
        hl = _esc(a.get("headline") or "Untitled")
        sub = _esc(a.get("subhead") or "")
        when = _esc(a.get("filed") or a.get("timestamp") or "")
        photo = _esc(a.get("photo") or "")
        loc = _esc(a.get("location") or a.get("place") or "")
        desk = _esc(a.get("desk") or a.get("byline") or "Grove Street Herald")
        weather = _esc(a.get("weather") or "")
        thumb = ""
        if photo:
            thumb = (
                '<a class="thumbwrap" href="/news/%s">'
                '<img class="thumb" src="/photo/%s" alt=""></a>'
                % (aid, photo)
            )
        loc_badge = ('<span class="locbadge">%s</span>' % loc) if loc else ""
        deck = ('<div class="deck">%s</div>' % sub) if sub else ""
        wx = ('<div class="wx">%s</div>' % weather) if weather else ""
        rows.append(
            '<article class="card">%s<div class="body">'
            '<a class="hl" href="/news/%s">%s</a>%s'
            '<div class="meta">%s · %s %s</div>%s'
            "</div></article>"
            % (thumb, aid, hl, deck, when, desk, loc_badge, wx)
        )
    weather = _pick(_NEWS_WEATHER, int(time.time()) // 3600)
    html = (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<meta name=\"theme-color\" content=\"#0d0a08\">"
        "<title>Grove Street Herald</title>"
        "<style>"
        "body{margin:0;background:#1a1510;color:#f5e6c8;font-family:Georgia,'Times New Roman',serif;}"
        ".mast{background:#0d0a08;border-bottom:4px solid #c4a35a;padding:22px 16px;text-align:center;}"
        ".mast h1{margin:0;font-size:30px;letter-spacing:3px;color:#c4a35a;font-variant:small-caps;}"
        ".mast .sub{font-size:12px;color:#a89060;margin-top:8px;letter-spacing:1px;}"
        ".weather{max-width:760px;margin:14px auto 0;padding:12px 16px;background:#241c14;"
        "border:1px solid #c4a35a;font-size:13px;color:#e8d4a8;}"
        ".wrap{max-width:760px;margin:0 auto;padding:8px 16px 48px;}"
        ".card{display:flex;gap:16px;padding:18px 0;border-bottom:1px solid #3a2e22;}"
        ".thumbwrap{flex:0 0 auto;}"
        ".thumb{width:112px;height:84px;object-fit:cover;border:2px solid #c4a35a;background:#000;display:block;}"
        ".hl{color:#fff8e8;font-size:19px;font-weight:bold;text-decoration:none;line-height:1.3;display:block;}"
        ".hl:hover{color:#c4a35a;}"
        ".deck{font-size:14px;color:#d4c09a;margin-top:8px;line-height:1.45;}"
        ".meta{font-size:11px;color:#a89060;margin-top:10px;line-height:1.5;}"
        ".locbadge{display:inline-block;margin-left:6px;padding:2px 8px;border:1px solid #c4a35a;"
        "background:#2a1a08;color:#f5e6c8;font-size:11px;font-weight:bold;letter-spacing:0.5px;}"
        ".wx{font-size:11px;color:#c4a35a;margin-top:6px;font-style:italic;}"
        ".empty{color:#a89060;line-height:1.55;padding:24px 8px;}"
        ".empty h2{color:#c4a35a;margin:0 0 10px;font-size:18px;}"
        ".nav{text-align:center;margin:20px;font-size:13px;}"
        ".nav a{color:#c4a35a;}"
        "@media(max-width:520px){.card{flex-direction:column;}.thumb{width:100%;height:160px;}}"
        "</style></head><body>"
        "<div class=\"mast\"><h1>Grove Street Herald</h1>"
        "<div class=\"sub\">Los Santos · San Andreas · Satirical edition · Offline templates</div></div>"
        "<div class=\"weather\"><b>Los Santos Weather:</b> __WEATHER__</div>"
        "<div class=\"wrap\">__ROWS__</div>"
        "<div class=\"nav\"><a href=\"/\">&larr; Back to GroveLink phone</a>"
        " · <a href=\"/recap\">Recap</a> · <a href=\"/qr\">Share URL</a></div>"
        "</body></html>"
    )
    # Escape literal % in CSS (100%) for safety if anyone switches back to % formatting
    return html.replace("__WEATHER__", _esc(weather)).replace("__ROWS__", "\n".join(rows))


def render_news_article_page(art_id):
    art = load_news_article(art_id)
    if not art:
        return None
    hl = _esc(art.get("headline") or "")
    sub = _esc(art.get("subhead") or "")
    byline = _esc(art.get("byline") or "")
    dateline = _esc(art.get("dateline") or "")
    pull = _esc(art.get("pull_quote") or "")
    related = _esc(art.get("related") or "")
    credit = _esc(art.get("photo_credit") or "")
    body_raw = art.get("body") or ""
    paras = []
    for block in str(body_raw).split("\n\n"):
        block = block.strip()
        if not block:
            continue
        paras.append("<p>%s</p>" % _esc(block).replace("\n", "<br>\n"))
    body = "\n".join(paras) if paras else ("<p>%s</p>" % _esc(body_raw).replace("\n", "<br>\n"))
    photo = _esc(art.get("photo") or "")
    when = _esc(art.get("filed") or art.get("timestamp") or "")
    weather = _esc(art.get("weather") or "")
    caption = _esc(art.get("caption") or "")
    loc = _esc(art.get("location") or art.get("place") or "")
    loc_html = ('<div class="locbadge">%s</div>' % loc) if loc else ""
    sub_html = ('<p class="subhead">%s</p>' % sub) if sub else ""
    date_html = ('<div class="dateline">%s</div>' % dateline) if dateline else ""
    pull_html = ('<blockquote class="pull">%s</blockquote>' % pull) if pull else ""
    related_html = ('<aside class="related">%s</aside>' % related) if related else ""
    credit_html = ('<div class="credit">%s</div>' % credit) if credit else ""
    img = ""
    if photo:
        img = (
            '<figure><img src="/photo/%s" alt="story photo">'
            '<figcaption>%s</figcaption></figure>'
            % (photo, caption or photo)
        )
    html = (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<meta name=\"theme-color\" content=\"#0d0a08\">"
        "<title>__HL__ - Grove Street Herald</title>"
        "<style>"
        "body{margin:0;background:#1a1510;color:#f5e6c8;font-family:Georgia,'Times New Roman',serif;}"
        ".mast{background:#0d0a08;border-bottom:4px solid #c4a35a;padding:16px;text-align:center;}"
        ".mast h1{margin:0;font-size:22px;letter-spacing:2px;color:#c4a35a;font-variant:small-caps;}"
        ".wrap{max-width:700px;margin:0 auto;padding:22px 18px 56px;}"
        "h2{font-size:28px;line-height:1.25;margin:0 0 10px;color:#fff8e8;}"
        ".subhead{font-size:17px;color:#d4c09a;line-height:1.45;margin:0 0 14px;font-style:italic;}"
        ".by{font-size:13px;color:#a89060;margin-bottom:6px;}"
        ".dateline{font-size:12px;color:#c4a35a;letter-spacing:0.5px;margin-bottom:14px;font-weight:bold;}"
        ".locbadge{display:inline-block;margin:0 0 16px;padding:4px 12px;border:1px solid #c4a35a;"
        "background:#2a1a08;color:#f5e6c8;font-size:13px;font-weight:bold;}"
        "figure{margin:0 0 18px;}"
        "figure img{width:100%;display:block;border:3px solid #c4a35a;background:#000;}"
        "figcaption{font-size:12px;color:#a89060;margin-top:8px;font-style:italic;}"
        ".pull{margin:20px 0;padding:14px 18px;border-left:4px solid #c4a35a;background:#241c14;"
        "font-size:18px;line-height:1.45;color:#fff0d0;font-style:italic;}"
        ".story{font-size:16px;line-height:1.7;color:#f0e2c4;}"
        ".story p{margin:0 0 1em;}"
        ".weather{margin:20px 0;padding:12px 14px;border:1px solid #c4a35a;background:#241c14;"
        "font-size:13px;color:#e8d4a8;}"
        ".related{margin:18px 0;padding:12px 14px;border:1px dashed #c4a35a;background:#1e1810;"
        "font-size:13px;color:#d4c09a;}"
        ".credit{font-size:11px;color:#a89060;margin-top:8px;font-style:italic;}"
        ".nav{margin-top:28px;font-size:13px;}"
        ".nav a{color:#c4a35a;margin-right:8px;}"
        "</style></head><body>"
        "<div class=\"mast\"><h1>Grove Street Herald</h1></div>"
        "<div class=\"wrap\">"
        "<h2>__HL2__</h2>"
        "__SUB__"
        "<div class=\"by\">__BY__ · Filed __WHEN__</div>"
        "__DATE__"
        "__LOC__"
        "__IMG__"
        "__PULL__"
        "<div class=\"story\">__BODY__</div>"
        "__CREDIT__"
        "<div class=\"weather\"><b>Los Santos Weather:</b> __WX__</div>"
        "__RELATED__"
        "<div class=\"nav\"><a href=\"/news\">&larr; All stories</a>"
        "<a href=\"/\">Phone feed</a><a href=\"/recap\">Recap</a> "
        "<button type=\"button\" id=\"share_article\" style=\"background:#2a1a08;color:#f5e6c8;"
        "border:1px solid #c4a35a;padding:8px 12px;font-weight:bold;cursor:pointer;min-height:40px\">"
        "Share article</button></div>"
        "</div>"
        "<script>"
        "(function(){"
        "var btn=document.getElementById('share_article');"
        "if(!btn)return;"
        "btn.onclick=function(){"
        "  var url=window.location.href;"
        "  var title=document.title||'Grove Street Herald';"
        "  function fallback(){"
        "    function ok(){btn.textContent='Copied!';setTimeout(function(){btn.textContent='Share article';},1500);}"
        "    if(navigator.clipboard&&navigator.clipboard.writeText){navigator.clipboard.writeText(url).then(ok).catch(function(){prompt('Copy URL',url);});}"
        "    else{prompt('Copy URL',url);}"
        "  }"
        "  if(navigator.share){navigator.share({title:title,url:url,text:title}).catch(fallback);}"
        "  else{fallback();}"
        "};"
        "})();"
        "</script>"
        "</body></html>"
    )
    return (
        html.replace("__HL__", hl)
        .replace("__HL2__", hl)
        .replace("__SUB__", sub_html)
        .replace("__BY__", byline)
        .replace("__WHEN__", when)
        .replace("__DATE__", date_html)
        .replace("__LOC__", loc_html)
        .replace("__IMG__", img)
        .replace("__PULL__", pull_html)
        .replace("__BODY__", body)
        .replace("__CREDIT__", credit_html)
        .replace("__WX__", weather)
        .replace("__RELATED__", related_html)
    )


def attach_captions_to_photos(photos):
    """Enrich photo dicts with caption field from JSON index / sidecars."""
    caps = load_captions()
    out = []
    for p in photos or []:
        if not isinstance(p, dict):
            out.append(p)
            continue
        item = dict(p)
        name = item.get("file") or ""
        cap = caps.get(name) or ""
        if not cap and name:
            side = os.path.join(WEB_PHOTOS, name + ".txt")
            if os.path.isfile(side):
                try:
                    with open(side, "r") as f:
                        cap = f.read().strip()[:200]
                except Exception:
                    cap = ""
        item["caption"] = cap
        out.append(item)
    return out


# --- 2.0.0 favorites + HUD helpers ---

def load_favorites():
    """Set of favorited photo basenames (JSON list under bridge)."""
    data = _load_json_file(FAVORITES_PATH, [])
    out = set()
    if isinstance(data, list):
        for name in data:
            n = _safe_basename(name)
            if n:
                out.add(n)
    elif isinstance(data, dict):
        for name, flag in data.items():
            if flag:
                n = _safe_basename(name)
                if n:
                    out.add(n)
    return out


def save_favorites(names):
    cleaned = sorted(set(_safe_basename(n) for n in (names or []) if _safe_basename(n)))
    return _save_json_file(FAVORITES_PATH, cleaned)


def set_favorite(name, on):
    name = _safe_basename(name)
    if not name:
        return False, "bad name"
    favs = load_favorites()
    if on:
        favs.add(name)
    else:
        favs.discard(name)
    ok = save_favorites(favs)
    return ok, name


def attach_favorites_to_photos(photos):
    favs = load_favorites()
    out = []
    for p in photos or []:
        if not isinstance(p, dict):
            out.append(p)
            continue
        item = dict(p)
        name = item.get("file") or ""
        item["favorite"] = bool(name and name in favs)
        out.append(item)
    return out



# --- 2.1.0 spectate viewers + photo locations ---

def note_spectate_viewer(ip):
    """Record a spectate poll from client IP; prune stale entries (~30s)."""
    now = time.time()
    viewers = STATE.get("spectate_viewers")
    if not isinstance(viewers, dict):
        viewers = {}
    ip = (ip or "").strip()
    if ip:
        viewers[ip] = now
    cutoff = now - SPECTATE_VIEWER_WINDOW
    pruned = {}
    for k, v in viewers.items():
        try:
            if float(v) >= cutoff:
                pruned[k] = v
        except Exception:
            pass
    STATE["spectate_viewers"] = pruned
    return len(pruned)


def spectate_watching_count():
    """How many distinct IPs polled spectate within the window."""
    return note_spectate_viewer("")


_KNOWN_SA_PLACES = (
    "Grove Street", "Ganton", "Idlewood", "LS Airport", "East Beach",
    "Vinewood", "Los Santos", "San Fierro", "Las Venturas", "Mount Chiliad",
    "Angel Pine", "Area 69", "Verdant Meadows", "Flint County", "Red County",
    "Jefferson", "Willowfield", "Ocean Docks", "Doherty", "Garcia",
    "Calton Heights", "Palomino Creek", "Blueberry", "Montgomery",
)


def location_from_caption(caption):
    """Pull a place tag from caption: loc:/#/@/📍 or known SA place name."""
    cap = (caption or "").strip()
    if not cap:
        return ""
    low = cap.lower()

    def _best_known(text):
        best = ""
        tlow = (text or "").lower()
        for place in sorted(_KNOWN_SA_PLACES, key=len, reverse=True):
            if place.lower() in tlow and len(place) > len(best):
                best = place
        return best

    # Explicit prefixes: loc:Place  #Place  @Place  📍Place
    for prefix in ("loc:", "location:", "#", "@", "📍"):
        if prefix == "📍":
            idx = cap.find("📍")
        else:
            idx = low.find(prefix)
        if idx < 0:
            continue
        start_i = idx + len(prefix)
        frag = cap[start_i:].strip()
        for sep in (",", "|", ";", chr(10)):
            if sep in frag:
                frag = frag.split(sep, 1)[0]
        frag = frag.strip().strip("#@").strip()[:48]
        if not frag:
            continue
        known = _best_known(frag)
        if known:
            return normalize_location(known)
        if " " not in frag:
            return normalize_location(frag)
        words = frag.split()
        return normalize_location(" ".join(words[:3])[:48])
    best = _best_known(cap)
    return normalize_location(best) if best else ""


def build_photo_location_map():
    """photo basename -> location from Herald articles that tagged a place."""
    locmap = {}
    try:
        arts = list_news_articles(100)
    except Exception:
        arts = []
    for art in arts:
        if not isinstance(art, dict):
            continue
        photo = _safe_basename(art.get("photo") or "")
        loc = normalize_location(art.get("location") or "")
        if photo and loc:
            locmap[photo] = loc
    return locmap


def attach_locations_to_photos(photos):
    """Enrich photos with location from news articles or caption tags."""
    news_map = build_photo_location_map()
    out = []
    for p in photos or []:
        if not isinstance(p, dict):
            out.append(p)
            continue
        item = dict(p)
        name = item.get("file") or ""
        loc = ""
        if name and name in news_map:
            loc = news_map[name]
        if not loc:
            loc = location_from_caption(item.get("caption") or "")
        item["location"] = loc or ""
        out.append(item)
    return out


def places_summary(photos):
    """List {place, count} for photos that have a location, sorted by count."""
    counts = {}
    for p in photos or []:
        if not isinstance(p, dict):
            continue
        loc = (p.get("location") or "").strip()
        if not loc:
            continue
        counts[loc] = counts.get(loc, 0) + 1
    items = [{"place": k, "count": counts[k]} for k in counts]
    items.sort(key=lambda x: (-int(x["count"]), x["place"].lower()))
    return items


def read_hud_from_ini(ini=None):
    """Read safe STATUS HUD fields written by CLEO (crash-safer ints/strings)."""
    ini = ini or STATE.get("link_ini") or ""
    hud = {
        "wanted": 0,
        "money": 0,
        "zone": "",
        "hour": -1,
        "spectate": False,
        "bridge": False,
    }
    if not ini or not os.path.isfile(ini):
        return hud
    try:
        wanted = read_ini_key(ini, "STATUS", "wanted", "0")
        money = read_ini_key(ini, "STATUS", "money", "0")
        zone = read_ini_key(ini, "STATUS", "zone", "")
        hour = read_ini_key(ini, "STATUS", "hour", "-1")
        spectate = read_ini_key(ini, "STATUS", "spectate", "0")
        # also mirror SPECTATE.on if STATUS.spectate missing
        if spectate in ("", "0"):
            spectate = read_ini_key(ini, "SPECTATE", "on", "0")
        bridge = read_ini_key(ini, "STATUS", "bridge", "0")
        try:
            hud["wanted"] = max(0, min(6, int(wanted)))
        except Exception:
            hud["wanted"] = 0
        try:
            hud["money"] = int(money)
        except Exception:
            hud["money"] = 0
        hud["zone"] = (zone or "").strip()[:48]
        try:
            hud["hour"] = int(hour)
        except Exception:
            hud["hour"] = -1
        if hud["hour"] < 0 or hud["hour"] > 23:
            # -1 means unset / CLEO skipped
            if str(hour).strip() in ("", "-1"):
                hud["hour"] = -1
            else:
                hud["hour"] = max(0, min(23, hud["hour"]))
        hud["spectate"] = str(spectate).strip() in ("1", "true", "yes", "on")
        hud["bridge"] = str(bridge).strip() in ("1", "true", "yes")
    except Exception:
        pass
    return hud


def render_manifest():
    """PWA-lite web app manifest (Add to Home Screen)."""
    ver = STATE.get("version", "unknown") or "unknown"
    return {
        "name": "GroveLink Phone",
        "short_name": "GroveLink",
        "description": "GTA SA camera gallery, texts to CJ, Herald, and spectate snapshots (v%s)." % ver,
        "start_url": "/",
        "scope": "/",
        "display": "standalone",
        "background_color": "#071109",
        "theme_color": "#071109",
        "orientation": "any",
        "lang": "en",
        "icons": [],
    }


# --- end 1.8.0 helpers ---


# HTML is assembled with placeholders for URLs injected at request time via
# a thin wrapper - keep static shell + JS that pulls /api for live data.
HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="theme-color" content="#071109">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="GroveLink">
<meta name="mobile-web-app-capable" content="yes">
<link rel="manifest" href="/manifest.webmanifest">
<title>GroveLink</title>
<style>
  body { margin:0; background:#050805; color:#d7ffd0; font-family: system-ui, -apple-system, Segoe UI, Arial, Helvetica, sans-serif; -webkit-font-smoothing:antialiased; }
  .shell { max-width: 460px; margin: 0 auto; min-height: 100vh; background:#0c140e; padding-bottom: 96px; box-shadow:0 0 0 1px #0a1a0c; }
  header { padding:18px 16px 16px; background:linear-gradient(180deg,#0a1610 0%,#071109 100%); border-bottom:2px solid #2cff6a; }
  h1 { margin:0; font-size:20px; letter-spacing:3px; color:#2cff6a; font-weight:800; }
  .sub { font-size:12px; color:#8bbb8b; margin-top:8px; line-height:1.55; max-width:36em; }
  .sect {
    margin:14px 12px 6px; font-size:11px; letter-spacing:2px; color:#2cff6a; font-weight:bold;
    text-transform:uppercase; opacity:0.95;
  }
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
  .stats { margin-top:14px; display:flex; gap:10px; flex-wrap:wrap; }
  .stat {
    flex:1; min-width:100px; background:#0b1a0e; border:1px solid #1f5a2a; padding:12px 12px;
    border-radius:4px;
  }
  .stat .k { font-size:10px; color:#7aaa7a; letter-spacing:1.5px; text-transform:uppercase; }
  .stat .v { font-size:22px; font-weight:800; color:#2cff6a; margin-top:6px; letter-spacing:0.5px; }
  .offline {
    display:none; margin:0; padding:14px 16px; background:#3a1212; border-bottom:2px solid #ff6a6a;
    color:#ffb0b0; font-size:14px; font-weight:bold; line-height:1.4; text-align:center;
  }
  .offline.show { display:block; }
  .composer {
    position:sticky; bottom:0; z-index:5; background:#0c140e; border-top:2px solid #2cff6a;
    padding:10px 12px 12px; box-shadow:0 -6px 16px rgba(0,0,0,0.35);
  }
  .composer .fromrow { display:flex; gap:8px; margin-bottom:8px; align-items:center; }
  .composer .fromrow label { font-size:11px; color:#7aaa7a; white-space:nowrap; }
  .composer .fromrow input {
    flex:1; padding:10px; border:1px solid #1a4; background:#0b0f0c; color:#d7ffd0;
    font-size:14px; min-height:40px; box-sizing:border-box;
  }
  .composer form { display:flex; gap:8px; padding:0; position:static; background:transparent; }
  input[type=text], input[type=search] {
    flex:1; padding:14px; border:1px solid #2cff6a; background:#0b0f0c; color:#d7ffd0;
    font-size:16px; min-height:48px; box-sizing:border-box;
  }
  button.send {
    background:#2cff6a; color:#041006; border:0; padding:14px 18px; font-weight:bold;
    font-size:16px; min-height:48px; min-width:88px;
  }
  .okmsg { padding:0 12px 8px; color:#2cff6a; font-size:12px; min-height:16px; }
  .chatbox {
    margin:10px 12px; padding:10px 12px; background:#0b0f0c; border:1px solid #1a4; border-radius:4px;
  }
  .chatbox h3 { margin:0 0 8px; font-size:12px; letter-spacing:1px; color:#2cff6a; }
  .chatmsg {
    background:#143; border:1px solid #1a4; border-radius:12px 12px 4px 12px;
    padding:8px 12px; margin:6px 0; font-size:13px; line-height:1.4;
  }
  .chatmsg.visitor {
    background:#143; border:1px solid #1a4; border-radius:12px 12px 4px 12px;
    margin-right:18%;
  }
  .chatmsg.cj {
    background:#1a2a40; border:1px solid #4af; border-radius:12px 12px 12px 4px;
    margin-left:18%; text-align:left;
  }
  .chatmsg.cj .who { color:#7abfff; }
  .chatmsg .who { font-size:10px; color:#7aaa7a; margin-bottom:2px; }
  .chatmsg .deliv { font-size:10px; color:#2cff6a; margin-top:4px; }
  .chatmsg.cj .deliv { color:#7abfff; }
  .chatempty { font-size:12px; color:#7aaa7a; }
  .chatmsg .reacts { margin-top:6px; display:flex; flex-wrap:wrap; gap:4px; align-items:center; }
  .chatmsg .reacts button {
    background:#0b0f0c; border:1px solid #1a4; color:#d7ffd0; font-size:12px;
    padding:4px 8px; border-radius:12px; cursor:pointer; min-height:28px;
  }
  .chatmsg .reacts button:active { border-color:#2cff6a; }
  .chatmsg .reacts .pinbtn { border-color:#c4a35a; color:#f5e6c8; }
  .chatmsg.pinned {
    outline:1px solid #c4a35a; box-shadow:0 0 0 1px rgba(196,163,90,0.35);
  }
  .chatpin {
    display:none; margin:0 0 10px; padding:8px 10px; background:#1a1508;
    border:1px solid #c4a35a; border-radius:4px; font-size:13px;
  }
  .chatpin.show { display:block; }
  .chatpin .plab { font-size:10px; letter-spacing:1px; color:#c4a35a; margin-bottom:4px; }
  .uptimefoot { color:#7aaa7a; font-size:11px; margin-top:6px; }
  .uptimefoot b { color:#2cff6a; }
  .spectate-link {
    display:inline-block; margin:8px 12px; padding:8px 12px; background:#1a2a40;
    border:1px solid #4af; color:#9cf; text-decoration:none; font-size:12px; font-weight:bold;
    letter-spacing:1px; border-radius:2px;
  }
  .spectate-link:hover { background:#243550; color:#fff; }
  .hero {
    margin:12px; background:#000; border:2px solid #2cff6a; position:relative; border-radius:2px;
    overflow:hidden;
  }
  .hero.unread { box-shadow:0 0 0 2px rgba(44,255,106,0.35); }
  .hero .badge {
    position:absolute; top:10px; left:10px; background:#2cff6a; color:#041006;
    font-size:11px; font-weight:bold; padding:5px 10px; letter-spacing:1px; z-index:1;
  }
  .hero a.imgwrap { display:block; }
  .hero img { width:100%; display:block; max-height:52vh; object-fit:cover; cursor:zoom-in; }
  .hero .meta, .shot .meta {
    padding:10px 12px; font-size:12px; color:#7aaa7a; display:flex; flex-wrap:wrap; gap:8px; align-items:center;
    background:#0b120e;
  }
  .meta .grow { flex:1; min-width:120px; }
  .caprow { display:flex; gap:8px; padding:0 12px 10px; background:#0b120e; align-items:center; }
  .caprow input {
    flex:1; padding:10px; border:1px solid #1a4; background:#0b0f0c; color:#d7ffd0;
    font-size:13px; min-height:40px; box-sizing:border-box;
  }
  .capbtn, .newsbtn, .sharebtn, .delbtn {
    background:#143; color:#d7ffd0; border:1px solid #2cff6a; padding:10px 12px;
    font-size:12px; font-weight:bold; min-height:40px; cursor:pointer; white-space:nowrap;
  }
  .newsbtn { background:#2a1a08; border-color:#c4a35a; color:#f5e6c8; }
  .delbtn {
    background:#3a1212; color:#ffb0b0; border:1px solid #a44;
  }
  .grid {
    display:grid; grid-template-columns:1fr 1fr; gap:10px; padding:0 12px 12px;
  }
  @media (min-width:420px) {
    .grid { grid-template-columns:1fr 1fr; }
  }
  .shot {
    margin:0; background:#000; border:1px solid #1a4; position:relative; border-radius:2px; overflow:hidden;
  }
  .shot.unread { border-color:#2cff6a; box-shadow:0 0 0 2px rgba(44,255,106,0.35); }
  .shot .badge {
    position:absolute; top:6px; left:6px; background:#2cff6a; color:#041006;
    font-size:9px; font-weight:bold; padding:3px 6px; letter-spacing:1px; z-index:1;
  }
  .shot a.imgwrap { display:block; }
  .shot img { width:100%; display:block; aspect-ratio:1; object-fit:cover; cursor:zoom-in; }
  .shot .meta { padding:8px; font-size:10px; gap:6px; }
  .shot .caprow { padding:0 8px 8px; flex-wrap:wrap; }
  .shot .caprow input { min-height:36px; font-size:12px; }
  .shot .btns { display:flex; flex-wrap:wrap; gap:6px; padding:0 8px 8px; background:#0b120e; }
  .hero .btns { display:flex; flex-wrap:wrap; gap:8px; padding:0 12px 12px; background:#0b120e; }
  .sectionlab {
    margin:4px 12px 8px; font-size:11px; letter-spacing:2px; color:#2cff6a; font-weight:bold;
  }
  .empty { padding:28px 18px; color:#8bbb8b; line-height:1.6; background:#0a120c; margin:12px; border:1px dashed #1f5a2a; border-radius:6px; }
  .empty h2 { margin:0 0 12px; color:#2cff6a; font-size:15px; letter-spacing:2px; font-weight:800; }
  .empty p { margin:0 0 10px; }
  .empty ol { margin:12px 0 0; padding-left:22px; }
  .empty li { margin:8px 0; }
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
  #news_dlg {
    display:none; position:fixed; inset:0; background:rgba(0,0,0,0.82);
    z-index:100; align-items:center; justify-content:center; padding:16px;
  }
  #news_dlg.show { display:flex; }
  #news_dlg .panel {
    width:100%; max-width:380px; background:#10180f; border:2px solid #c4a35a;
    padding:22px 18px; text-align:center; box-sizing:border-box;
  }
  #news_dlg h2 { margin:0 0 8px; color:#c4a35a; font-size:18px; letter-spacing:1px; }
  #news_dlg p { margin:0 0 12px; color:#7aaa7a; font-size:13px; line-height:1.45; }
  #news_dlg label { display:block; text-align:left; font-size:11px; color:#a89060; margin:8px 0 4px; }
  #news_dlg select, #news_dlg input {
    width:100%; box-sizing:border-box; padding:12px; border:1px solid #c4a35a;
    background:#0b0f0c; color:#f5e6c8; font-size:15px; min-height:44px;
  }
  #news_dlg .btns { display:flex; gap:12px; margin-top:16px; }
  #news_dlg .btns button {
    flex:1; min-height:56px; font-size:16px; font-weight:bold; border:0; cursor:pointer;
    padding:14px 12px;
  }
  #news_dlg .btn-go { background:#c4a35a; color:#1a1510; }
  #news_dlg .btn-cancel { background:#1a2a1a; color:#d7ffd0; border:1px solid #2cff6a; }
  .helpfoot {
    margin:8px 12px 20px; padding:12px 14px; background:#0b0f0c; border:1px solid #1a4;
    font-size:11px; color:#7aaa7a; line-height:1.55; border-radius:2px;
  }
  .helpfoot strong { color:#2cff6a; }
  .helpfoot kbd {
    display:inline-block; padding:1px 6px; border:1px solid #2cff6a; color:#2cff6a;
    font-family:Arial,sans-serif; font-size:10px; border-radius:2px; margin:0 1px;
  }
  .helpfoot .help-detail { margin-top:8px; padding-top:8px; border-top:1px solid #1a4; display:none; }
  .helpfoot .help-detail.show { display:block; }
  .helpfoot .helptoggle {
    background:none; border:0; color:#2cff6a; font-size:11px; font-weight:bold;
    cursor:pointer; padding:0; text-decoration:underline; min-height:28px;
  }

  .hudstrip {
    margin-top:10px; padding:10px 12px; background:#0b1a0e; border:1px solid #1a4;
    font-size:12px; color:#b6e6b0; display:flex; flex-wrap:wrap; gap:10px; align-items:center;
  }
  .hudstrip .huditem { white-space:nowrap; }
  .hudstrip .hudk { color:#7aaa7a; margin-right:4px; }
  .hudstrip .hudv { color:#2cff6a; font-weight:bold; }
  .hudstrip.hidden { display:none; }
  .timestrip {
    margin-top:8px; font-size:12px; color:#7aaa7a; letter-spacing:1px;
  }
  .timestrip strong { color:#2cff6a; }
  .timestrip.hidden { display:none; }
  .quickbar {
    display:flex; gap:8px; margin:10px 12px 0; flex-wrap:wrap;
  }
  .quickbar a, .quickbar button {
    flex:1; min-width:100px; background:#143; color:#d7ffd0; border:1px solid #2cff6a;
    padding:10px 8px; font-size:11px; font-weight:bold; min-height:44px; cursor:pointer;
    text-decoration:none; text-align:center; display:inline-flex; align-items:center; justify-content:center;
    box-sizing:border-box; border-radius:2px;
  }
  .quickbar a.qa-herald { border-color:#c4a35a; color:#f5e6c8; background:#2a1a08; }
  .quickbar a.qa-recap { border-color:#2cff6a; color:#b6e6b0; background:#0b1a10; }
  .quickbar a.qa-spec { border-color:#4af; color:#9cf; background:#1a2a40; }
  .favbtn {
    background:#143; color:#d7ffd0; border:1px solid #2cff6a; padding:10px 12px;
    font-size:12px; font-weight:bold; min-height:40px; cursor:pointer; white-space:nowrap;
  }
  .favbtn.on { background:#2a2208; border-color:#c4a35a; color:#ffd86a; }
  .chathead { display:flex; align-items:center; gap:8px; margin:0 0 8px; }
  .chathead h3 { margin:0; flex:1; font-size:12px; letter-spacing:1px; color:#2cff6a; }
  .chatbadge {
    display:none; min-width:20px; padding:2px 7px; border-radius:10px; background:#e22; color:#fff;
    font-size:11px; font-weight:bold; text-align:center;
  }
  .chatbadge.show { display:inline-block; }
  .chatacts { display:flex; gap:6px; flex-wrap:wrap; margin-bottom:8px; }
  .chatacts button {
    background:#1a2a1a; color:#d7ffd0; border:1px solid #2cff6a; padding:8px 10px;
    font-size:11px; font-weight:bold; min-height:36px; cursor:pointer;
  }
  .newslink {
    display:inline-block; margin-top:8px; padding:8px 12px; border:1px solid #c4a35a;
    color:#f5e6c8; background:#2a1a08; text-decoration:none; font-size:12px; font-weight:bold;
  }
  .toast {
    display:none; position:fixed; top:18px; left:50%; transform:translateX(-50%);
    z-index:200; background:#3a1212; color:#ffb0b0; border:2px solid #ff6a6a;
    padding:12px 18px; font-size:14px; font-weight:bold; letter-spacing:1px;
    box-shadow:0 6px 20px rgba(0,0,0,0.45); max-width:90%; text-align:center;
  }
  .toast.show { display:block; animation: toastIn 0.25s ease-out; }
  @keyframes toastIn { from { opacity:0; transform:translateX(-50%) translateY(-8px);} to { opacity:1; transform:translateX(-50%) translateY(0);} }
  .moments {
    margin:10px 0 4px; padding:0 12px 8px; overflow-x:auto; -webkit-overflow-scrolling:touch;
    display:none; white-space:nowrap;
  }
  .moments.show { display:block; }
  .moments .mlab {
    font-size:11px; letter-spacing:2px; color:#2cff6a; font-weight:bold; margin:0 0 8px; display:block;
  }
  .moments .mrow { display:inline-flex; gap:10px; }
  .moments .mcell {
    display:inline-block; width:72px; text-align:center; cursor:pointer; vertical-align:top;
  }
  .moments .mring {
    width:68px; height:68px; border-radius:50%; border:3px solid #2cff6a;
    overflow:hidden; margin:0 auto 4px; background:#000; box-sizing:border-box;
    box-shadow:0 0 0 2px rgba(44,255,106,0.25);
  }
  .moments .mring img { width:100%; height:100%; object-fit:cover; display:block; }
  .moments .mlabel { font-size:9px; color:#7aaa7a; overflow:hidden; text-overflow:ellipsis; max-width:72px; }
  .watching {
    display:none; margin:6px 12px 0; font-size:12px; color:#9cf; font-weight:bold; letter-spacing:0.5px;
  }
  .watching.show { display:block; }

  .modebar { display:flex; gap:8px; align-items:center; flex-wrap:wrap; margin:8px 0 4px; }
  .modebar button {
    background:#123012; color:#9fdf9f; border:1px solid #2a5a2a; border-radius:999px;
    padding:6px 12px; font-size:12px; cursor:pointer;
  }
  .modebar button.on { background:#1a4a1a; border-color:#2ecc71; color:#7CFF7C; font-weight:700; }
  .modebar .tip { font-size:11px; color:#7aaa7a; }
  .viewers { margin:6px 0 10px; padding:8px 10px; background:#0d1f0d; border:1px solid #1a3a1a; border-radius:10px; font-size:12px; }
  .viewers .vl { color:#7CFF7C; font-weight:700; margin-bottom:4px; }
  .viewers .chips { display:flex; flex-wrap:wrap; gap:6px; }
  .viewers .vchip { background:#143214; border:1px solid #2a5a2a; color:#c8f0c8; padding:3px 8px; border-radius:999px; font-size:11px; }
  .viewers .emptyv { color:#6a9a6a; font-style:italic; }
  .reqbar, .pollbox, .hostpanel {
    margin:8px 0 12px; padding:10px 12px; background:#0d1f0d; border:1px solid #1a4a1a; border-radius:12px;
  }
  .reqbar h4, .pollbox h4, .hostpanel h4 { margin:0 0 8px; font-size:13px; color:#7CFF7C; letter-spacing:0.04em; }
  .reqbar .reqbtns { display:flex; flex-wrap:wrap; gap:8px; }
  .reqbar button, .hostpanel button, .pollbox button {
    background:#123012; color:#c8f0c8; border:1px solid #2ecc71; border-radius:8px; padding:8px 10px; font-size:12px; cursor:pointer;
  }
  .reqbar button:active { background:#1a4a1a; }
  .pollopt { display:block; width:100%; text-align:left; margin:4px 0; }
  .pollopt .cnt { float:right; color:#7CFF7C; }
  .pollq { font-size:14px; margin-bottom:8px; }
  .host-only { display:none; }
  body.mode-host .host-only { display:block; }
  body.mode-host .viewer-only { display:none; }
  .hostpanel textarea, .hostpanel input[type=text] {
    width:100%; box-sizing:border-box; margin:4px 0 8px; padding:8px; border-radius:8px;
    border:1px solid #2a5a2a; background:#061206; color:#c8f0c8; font-size:13px;
  }
  .reqlist { list-style:none; margin:0; padding:0; }
  .reqlist li { display:flex; justify-content:space-between; gap:8px; align-items:center;
    padding:6px 0; border-bottom:1px solid #1a3a1a; font-size:12px; }
  .reqlist .donebtn { padding:4px 8px; font-size:11px; }
  .empty-host { color:#6a9a6a; font-size:12px; font-style:italic; }

  .quickbar .qa-watch {
    flex:0 0 auto; min-width:90px; border-color:#4af; color:#9cf; background:#1a2a40; pointer-events:none;
  }
  .placelist { margin:8px 12px 16px; }
  .placeitem {
    display:flex; align-items:center; justify-content:space-between; gap:10px;
    padding:14px 12px; margin:6px 0; background:#0b0f0c; border:1px solid #1a4;
    cursor:pointer; min-height:48px; font-size:14px; color:#d7ffd0;
  }
  .placeitem:hover { border-color:#2cff6a; }
  .placeitem .pc { color:#2cff6a; font-weight:bold; }
  .placeback {
    margin:8px 12px; background:#143; color:#2cff6a; border:1px solid #2cff6a;
    padding:10px 12px; font-size:12px; font-weight:bold; min-height:40px; cursor:pointer;
  }
  .locbadge-mini {
    display:inline-block; margin-left:6px; padding:2px 6px; font-size:10px;
    background:#2a1a08; border:1px solid #c4a35a; color:#f5e6c8; border-radius:2px;
  }
  .commentrow { display:flex; gap:8px; padding:0 12px 10px; background:#0b120e; align-items:center; }
  .commentrow input {
    flex:1; padding:10px; border:1px solid #1a4; background:#0b0f0c; color:#b6e6b0;
    font-size:13px; min-height:40px; box-sizing:border-box;
  }
  .commentrow .capbtn { white-space:nowrap; }
  .commentshow {
    padding:0 12px 8px; background:#0b120e; color:#9cbf9c; font-size:12px; font-style:italic;
    min-height:0;
  }
  .commentshow:empty { display:none; }
  .prefs {
    display:flex; gap:8px; margin:8px 12px 0; flex-wrap:wrap; align-items:center;
  }
  .prefs button {
    background:#143; color:#d7ffd0; border:1px solid #2cff6a; padding:8px 12px;
    font-size:11px; font-weight:bold; min-height:36px; cursor:pointer;
  }
  .prefs button.on { background:#2cff6a; color:#041006; }
  .streakstat .v { color:#ffd86a; }
  /* Density: dark street (default) vs bright grove green */
  body.density-dark {
    background:#070b08; color:#d7ffd0;
  }
  body.density-dark header { background:#071109; border-bottom-color:#2cff6a; }
  body.density-bright {
    background:#0e1a12; color:#e8ffe8;
  }
  body.density-bright header {
    background:#12301a; border-bottom-color:#5dff8a;
  }
  body.density-bright .livebadge { background:#1a8; }
  body.density-bright .stat .v, body.density-bright h1 { color:#5dff8a; }
  body.density-bright .quickbar a, body.density-bright .quickbar button,
  body.density-bright .actionbtn, body.density-bright .prefs button {
    border-color:#5dff8a; color:#e8ffe8; background:#1a4028;
  }
  body.density-bright .shot, body.density-bright .hero {
    border-color:#3a8a55;
  }
  body.density-bright .composer { background:#12301a; border-top-color:#5dff8a; }
</style>
</head>
<body>
<div class="shell">
  <div class="offline" id="offline_banner">Bridge offline - run START_GROVELINK</div>
  <header>
    <h1>GROVELINK <span class="livebadge" id="livebadge">LIVE</span></h1>
    <div class="sub">Photos from GTA San Andreas on this PC → your real phone · text CJ · file Breaking News</div>
    <div class="stats">
      <div class="stat"><div class="k">VERSION</div><div class="v" id="ver">__VERSION__</div></div>
      <div class="stat"><div class="k">PHOTOS</div><div class="v" id="count">0</div></div>
      <div class="stat streakstat"><div class="k">STREAK</div><div class="v" id="streak_val">0</div></div>
    </div>
    <div class="hudstrip hidden" id="hud_strip" title="Live second-screen HUD from GTA (STATUS.* in link.ini)">
      <span class="huditem"><span class="hudk">WANTED</span><span class="hudv" id="hud_wanted">-</span></span>
      <span class="huditem"><span class="hudk">$</span><span class="hudv" id="hud_money">-</span></span>
      <span class="huditem"><span class="hudk">ZONE</span><span class="hudv" id="hud_zone">-</span></span>
      <span class="huditem"><span class="hudk">SPEC</span><span class="hudv" id="hud_spec">off</span></span>
    </div>
    <div class="timestrip hidden" id="time_strip"><strong>SA TIME</strong> <span id="hud_hour">-</span></div>
    <div class="urls">
      <div class="urlrow">
        <span><strong>Phone (LAN):</strong> <span id="lan_url">__LAN_URL__</span></span>
        <button type="button" class="copybtn" id="copy_lan">Copy</button>
      </div>
      <div class="urlrow">
        <span><strong>This PC:</strong> <span id="local_url">__LOCAL_URL__</span></span>
        <button type="button" class="copybtn" id="copy_local">Copy</button>
      </div>
    </div>
    <div class="actions">
      <a class="actionbtn" id="dl_latest" href="#" target="_blank" rel="noopener" disabled style="opacity:0.4;pointer-events:none">Download latest</a>
      <a class="actionbtn" id="export_zip" href="#" disabled style="opacity:0.4;pointer-events:none">Export zip</a>
      <button type="button" class="actionbtn" id="share_page">Share page</button>
      <button type="button" class="actionbtn" id="mark_read">Mark all read</button>
      <button type="button" class="actionbtn" id="clear_all" disabled style="background:#3a1212;border-color:#a44;color:#ffb0b0">Clear all phone copies</button>
      <a class="actionbtn" id="news_index" href="/news" style="border-color:#c4a35a;color:#f5e6c8;background:#2a1a08">Grove Street Herald</a>
    </div>
    <div class="bigcopy" id="big_copy" title="Tap to copy IP:port">
      <div class="label">TAP TO COPY - PHONE ADDRESS</div>
      <div class="ipport" id="ip_port">__IP_PORT__</div>
      <div class="hint" id="big_copy_hint">Copies host:port for your phone browser</div>
    </div>
    <div class="smsnote">Same Wi-Fi + bridge running → CJ gets your texts in-game (K → INBOX). No QR lib - open <code>http://</code> + address above. Or <a id="sms_link" href="#">sms: note with URL</a>.</div>
    <div class="tip"><strong>Tip:</strong> Browser menu → <b>Add to Home Screen</b> (uses <code>/manifest.webmanifest</code>) for a one-tap icon.</div>
    <div class="status" id="skip_note" style="display:none;margin-top:6px">Hidden from phone: <span id="skip_count">0</span> (deleted skip list - Gallery untouched)</div>
    <div class="status">
      <span class="pulse live" id="pulse"></span>
      Bridge: <span id="bridge_status" class="ok">online</span>
      &nbsp;·&nbsp; Last poll: <span id="last_refresh">-</span>
      &nbsp;·&nbsp; <span id="refresh_hint">auto every 2s</span>
      &nbsp;·&nbsp; Unread: <span id="unread_count">0</span>
      <span id="last_error_hint" class="bad" style="display:none"></span>
    </div>
  </header>
  <div class="quickbar" id="quick_actions">
    <button type="button" id="qa_camera" title="Open GTA and press K → Camera">Camera tip</button>
    <a class="qa-spec" href="/spectate">Spectate</a>
    <a class="qa-herald" href="/news">Herald</a>
    <a class="qa-recap" href="/recap">Recap</a>
    <button type="button" id="qa_text">Text CJ</button>
    <a class="qa-recap" href="/live" title="Spectate + chat">Watch party</a>
    <span class="qa-watch" id="qa_watching" title="Spectate viewers (last ~30s)">0 watching</span>
  </div>
  <div class="watching" id="watching_note"></div>

  <div class="modebar" id="modebar">
    <button type="button" id="mode_viewer" class="on">Viewer</button>
    <button type="button" id="mode_host">Host</button>
    <span class="tip" id="mode_tip">Viewers chat, react, vote &amp; request. Host: moderate + broadcast + polls.</span>
  </div>
  <div class="viewers" id="viewers_box">
    <div class="vl">VIEWERS <span id="viewer_count">0</span></div>
    <div class="chips" id="viewer_chips"><span class="emptyv" id="viewers_empty">Waiting for viewers… share your LAN URL</span></div>
  </div>
  <div class="reqbar viewer-only" id="reqbar">
    <h4>ASK CJ</h4>
    <div class="reqbtns">
      <button type="button" data-kind="camera">Take a Camera pic</button>
      <button type="button" data-kind="news">Do a NEWS snap</button>
      <button type="button" data-kind="say_hi">Say hi</button>
      <button type="button" data-kind="spectate_on">Spectate on</button>
    </div>
  </div>
  <div class="pollbox" id="pollbox" style="display:none">
    <h4>LIVE POLL</h4>
    <div class="pollq" id="poll_q"></div>
    <div id="poll_opts"></div>
    <div class="empty-host" id="poll_closed" style="display:none"></div>
  </div>
  <div class="hostpanel host-only" id="hostpanel">
    <h4>HOST CONTROLS</h4>
    <div class="tip" style="margin-bottom:8px;font-size:11px;color:#7aaa7a">You are hosting — viewers on the same Wi-Fi use Viewer mode. Broadcast pushes a CJ message to everyone.</div>
    <label>Broadcast to all viewers</label>
    <input type="text" id="bcast_msg" maxlength="80" placeholder="CJ says…">
    <button type="button" id="bcast_btn">Broadcast</button>
    <label style="display:block;margin-top:10px">Create poll (2–4 options, | separated)</label>
    <input type="text" id="poll_question" maxlength="120" placeholder="Question…">
    <input type="text" id="poll_options" maxlength="160" placeholder="Grove|Ballas|Neutral">
    <button type="button" id="poll_create">Create poll</button>
    <button type="button" id="poll_close">Close poll → CJ inbox</button>
    <h4 style="margin-top:12px">Pending requests</h4>
    <ul class="reqlist" id="req_list"><li class="empty-host">No pending requests</li></ul>
    <button type="button" id="req_clear" style="margin-top:6px">Clear all pending</button>
  </div>
  <div class="prefs" id="prefs_bar">
    <button type="button" id="theme_dark" class="on" title="Dark street green">Dark street</button>
    <button type="button" id="theme_bright" title="Bright grove green">Bright</button>
  </div>
  <div class="sect">Companion chat</div>
  <div class="chatbox" id="chatbox">
    <div class="chathead">
      <h3>TEXTS TO CJ</h3>
      <span class="chatbadge" id="chat_unread" title="Unread CJ replies">0</span>
    </div>
    <div class="chatacts">
      <button type="button" id="chat_mark_read">Mark chat read</button>
      <button type="button" id="chat_notify_btn">Enable CJ alerts</button>
      <button type="button" id="chat_mute_btn" title="Mute chat notifications (localStorage)">Mute alerts</button>
    </div>
    <div class="chatpin" id="chat_pin"><div class="plab">PINNED</div><div id="chat_pin_body"></div></div>
    <div id="chat_thread"><div class="chatempty">Send a message below - delivered texts show here. CJ replies appear on the right.</div></div>
  </div>
  <div class="sect">Live view</div>
  <a class="spectate-link" href="/spectate">LIVE SPECTATE - snapshot view</a>
  <div class="chips">
    <button type="button" class="chip" data-msg="Where you at?">Where you at?</button>
    <button type="button" class="chip" data-msg="Nice shot">Nice shot</button>
    <button type="button" class="chip" data-msg="Come to Grove">Come to Grove</button>
  </div>
  <div class="okmsg" id="ok"></div>
  <div class="sect">Gallery</div>
  <div class="searchrow">
    <input id="search" type="search" placeholder="Search filename..." autocomplete="off">
  </div>
  <div class="tabs">
    <button type="button" class="tab on" id="tab_all" data-filter="all">All</button>
    <button type="button" class="tab" id="tab_today" data-filter="today">Today</button>
    <button type="button" class="tab" id="tab_fav" data-filter="favorites">Favorites</button>
    <button type="button" class="tab" id="tab_place" data-filter="places">By place</button>
    <button type="button" class="tab" id="tab_sort" data-sort="newest" title="Client-side only - server always sends newest first">Newest</button>
  </div>
  <div class="moments" id="moments_reel"></div>
  <div id="feed"></div>
  <div class="toast" id="toast" role="status" aria-live="polite"></div>
  <div class="helpfoot" id="help_foot">
    <div class="uptimefoot" id="uptime_foot">Bridge uptime: <b id="uptime_val">-</b></div>
    <div><strong>Shortcuts</strong> -
      <kbd>?</kbd> help ·
      <kbd>Esc</kbd> close lightbox ·
      <kbd>/</kbd> search ·
      <button type="button" class="helptoggle" id="help_toggle">more</button>
    </div>
    <div class="help-detail" id="help_detail">
      <div><strong>GTA:</strong> <kbd>K</kbd> phone · Up/Down menu · Enter/Space select · Backspace close · Camera snaps here · SMS notifies even if phone closed</div>
      <div><strong>This page:</strong> Hero + grid feed · Caption · Breaking News · Share · Export / Clear · Texts deliver to CJ via link.ini</div>
      <div><strong>Tip:</strong> Keep START_GROVELINK open; phone + PC on same Wi-Fi. Press <kbd>?</kbd> anytime.</div>
    </div>
  </div>
  <div class="composer" id="composer">
    <div class="fromrow">
      <label for="from_name">Nickname:</label>
      <input id="from_name" type="text" maxlength="40" value="REAL PHONE" placeholder="REAL PHONE" autocomplete="nickname" title="Saved in this browser; sent as from= with texts">
    </div>
    <form id="f">
      <input id="msg" type="text" maxlength="80" placeholder="Message to CJ..." required>
      <button class="send" type="submit">SEND</button>
    </form>
  </div>
</div>
<div id="lightbox" onclick="closeLb(event)">
  <button type="button" class="close" onclick="closeLb(event)">&times;</button>
  <img id="lbimg" src="" alt="full size">
</div>
<div id="confirm_dlg" onclick="confirmCancel(event)">
  <div class="panel" onclick="event.stopPropagation()">
    <h2>Delete this shot?</h2>
    <p id="confirm_detail">Removes it from the phone page only.<br>GTA Gallery file stays on the PC.</p>
    <div class="btns">
      <button type="button" class="btn-no" id="confirm_no">Cancel</button>
      <button type="button" class="btn-yes" id="confirm_yes">Delete</button>
    </div>
  </div>
</div>

<div id="news_dlg" onclick="newsDlgCancel(event)">
  <div class="panel" onclick="event.stopPropagation()">
    <h2>File Breaking News?</h2>
    <p>Optional San Andreas location tag for the Herald badge.</p>
    <label for="news_loc_sel">Place</label>
    <select id="news_loc_sel">
      <option value="">(optional - pick or type)</option>
      <option value="Grove Street">Grove Street</option>
      <option value="Ganton">Ganton</option>
      <option value="Idlewood">Idlewood</option>
      <option value="LS Airport">LS Airport</option>
      <option value="East Beach">East Beach</option>
      <option value="Vinewood">Vinewood</option>
      <option value="Los Santos">Los Santos</option>
      <option value="San Fierro">San Fierro</option>
      <option value="Las Venturas">Las Venturas</option>
      <option value="Mount Chiliad">Mount Chiliad</option>
      <option value="Angel Pine">Angel Pine</option>
      <option value="Area 69">Area 69</option>
      <option value="Verdant Meadows">Verdant Meadows</option>
      <option value="Flint County">Flint County</option>
      <option value="Red County">Red County</option>
    </select>
    <label for="news_loc_txt">Or type a location</label>
    <input id="news_loc_txt" type="text" maxlength="48" placeholder="e.g. Grove Street">
    <div class="btns">
      <button type="button" class="btn-cancel" id="news_cancel">Cancel</button>
      <button type="button" class="btn-go" id="news_go">File story</button>
    </div>
  </div>
</div>
<script>
var LS_KEY = 'grovelink_last_visit';
var LS_FAV = 'grovelink_favorites';
var LS_CHAT_READ = 'grovelink_chat_read_ts';
var LS_NICK = 'grovelink_nickname';

var LS_MODE = 'grovelink_mode'; // viewer | host
function getMode() {
  try { return localStorage.getItem(LS_MODE) || 'viewer'; } catch (e) { return 'viewer'; }
}
function setMode(m) {
  m = (m === 'host') ? 'host' : 'viewer';
  try { localStorage.setItem(LS_MODE, m); } catch (e) {}
  var cls = (document.body.className || '');
  var parts = cls.split(' ');
  var out = [];
  for (var i = 0; i < parts.length; i++) {
    if (parts[i] && parts[i].indexOf('mode-') !== 0) out.push(parts[i]);
  }
  document.body.className = (out.join(' ').trim() + ' mode-' + m).trim();
  var bv = document.getElementById('mode_viewer');
  var bh = document.getElementById('mode_host');
  if (bv) bv.className = (m === 'viewer') ? 'on' : '';
  if (bh) bh.className = (m === 'host') ? 'on' : '';
  var tip = document.getElementById('mode_tip');
  if (tip) tip.textContent = (m === 'host')
    ? 'Host: moderation, broadcast, poll, request queue.'
    : 'Viewer: chat, react, vote, request. Toggle Host if you run the game.';
}
function paintViewers(list) {
  list = list || [];
  var nEl = document.getElementById('viewer_count');
  if (nEl) nEl.textContent = String(list.length);
  var chips = document.getElementById('viewer_chips');
  if (!chips) return;
  if (!list.length) {
    chips.innerHTML = '<span class="emptyv" id="viewers_empty">Waiting for viewers… share your LAN URL</span>';
    return;
  }
  var h = '';
  for (var i = 0; i < list.length; i++) {
    var v = list[i] || {};
    h += '<span class="vchip">' + escapeHtml(v.nick || 'Viewer') + '</span>';
  }
  chips.innerHTML = h;
}
function paintPoll(poll) {
  var box = document.getElementById('pollbox');
  if (!box) return;
  if (!poll || !poll.question) { box.style.display = 'none'; return; }
  box.style.display = '';
  var q = document.getElementById('poll_q');
  if (q) q.textContent = poll.question;
  var opts = document.getElementById('poll_opts');
  var closed = document.getElementById('poll_closed');
  if (!opts) return;
  var tallies = poll.tallies || [];
  var h = '';
  for (var i = 0; i < tallies.length; i++) {
    var t = tallies[i] || {};
    if (poll.open) {
      h += '<button type="button" class="pollopt" data-idx="' + i + '">' + escapeHtml(t.label || ('#' + i)) +
           ' <span class="cnt">' + (t.votes || 0) + '</span></button>';
    } else {
      h += '<div class="pollopt">' + escapeHtml(t.label || ('#' + i)) +
           ' <span class="cnt">' + (t.votes || 0) + '</span></div>';
    }
  }
  opts.innerHTML = h;
  if (closed) {
    if (!poll.open) {
      closed.style.display = '';
      closed.textContent = poll.summary || 'Poll closed';
    } else {
      closed.style.display = 'none';
      closed.textContent = '';
    }
  }
  var buttons = opts.querySelectorAll('button.pollopt');
  for (var j = 0; j < buttons.length; j++) {
    buttons[j].onclick = (function(btn) {
      return function() { votePoll(btn.getAttribute('data-idx')); };
    })(buttons[j]);
  }
}
function paintRequests(pending) {
  var ul = document.getElementById('req_list');
  if (!ul) return;
  pending = pending || [];
  if (!pending.length) {
    ul.innerHTML = '<li class="empty-host">No pending requests</li>';
    return;
  }
  var h = '';
  for (var i = 0; i < pending.length; i++) {
    var r = pending[i] || {};
    h += '<li><span>' + escapeHtml(r.label || r.kind || '?') + ' · from ' + escapeHtml(r.from || '?') +
         '</span><button type="button" class="donebtn" data-id="' + escapeHtml(r.id || '') + '">Done</button></li>';
  }
  ul.innerHTML = h;
  var btns = ul.querySelectorAll('.donebtn');
  for (var k = 0; k < btns.length; k++) {
    btns[k].onclick = (function(b) {
      return function() { markRequestDone(b.getAttribute('data-id')); };
    })(btns[k]);
  }
}
function postForm(url, body, cb) {
  var x = new XMLHttpRequest();
  x.open('POST', url, true);
  x.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
  x.onreadystatechange = function() {
    if (x.readyState === 4) {
      var j = null;
      try { j = JSON.parse(x.responseText); } catch (e) { j = null; }
      if (cb) cb(x.status, j);
    }
  };
  x.send(body);
}
function sendRequest(kind) {
  saveNick();
  var frm = (document.getElementById('from_name').value || 'Viewer').trim() || 'Viewer';
  postForm('/request', 'kind=' + encodeURIComponent(kind) + '&from=' + encodeURIComponent(frm), function(st, j) {
    if (st === 200 && j && j.ok) flashOk('Request sent: ' + (j.request && j.request.label || kind));
    else flashOk((j && j.detail) || 'Request failed');
    poll();
  });
}
function votePoll(idx) {
  saveNick();
  var frm = (document.getElementById('from_name').value || '').trim();
  postForm('/vote', 'option=' + encodeURIComponent(idx) + '&from=' + encodeURIComponent(frm), function(st, j) {
    if (st === 200 && j && j.ok) flashOk('Vote recorded');
    else flashOk((j && j.detail) || 'Vote failed');
    poll();
  });
}
function markRequestDone(id) {
  postForm('/request', 'action=done&id=' + encodeURIComponent(id || ''), function(st, j) {
    flashOk((j && j.detail) || (st === 200 ? 'Done' : 'Failed'));
    poll();
  });
}
function doBroadcast() {
  var inp = document.getElementById('bcast_msg');
  var msg = (inp && inp.value || '').trim();
  if (!msg) { flashOk('Type a broadcast message'); return; }
  postForm('/broadcast', 'msg=' + encodeURIComponent(msg) + '&from=CJ', function(st, j) {
    if (st === 200 && j && j.ok) { flashOk('Broadcast sent'); if (inp) inp.value = ''; }
    else flashOk((j && j.detail) || 'Broadcast failed');
    poll();
  });
}
function doCreatePoll() {
  var q = (document.getElementById('poll_question').value || '').trim();
  var o = (document.getElementById('poll_options').value || '').trim();
  if (!q || !o) { flashOk('Need question + options (A|B|…)'); return; }
  postForm('/poll', 'question=' + encodeURIComponent(q) + '&options=' + encodeURIComponent(o), function(st, j) {
    if (st === 200 && j && j.ok) flashOk('Poll created');
    else flashOk((j && j.detail) || 'Poll failed');
    poll();
  });
}
function doClosePoll() {
  postForm('/poll', 'action=close', function(st, j) {
    flashOk((j && j.detail) || (st === 200 ? 'Poll closed' : 'No open poll'));
    poll();
  });
}

var LS_MUTE = 'grovelink_mute_chat';
var LS_DENSITY = 'grovelink_density';
var FILTER = 'all';
var SEARCH_Q = '';
var SORT_ORDER = 'newest'; // client-side only; server /api is always newest-first
var PLACE_FILTER = '';
var LAST_PHOTOS = [];
var LAST_PLACES = [];
var LAST_CHAT = [];
var PINNED_ID = '';
var LAST_HUD = null;
var LAST_WANTED = -1;
var PENDING_ACTION = ''; // 'delete:NAME' or 'clear'
var HERO_IDX = 0;
var PULL_Y = 0;
function emptyHtml() {
  var ipPort = '';
  try { ipPort = (document.getElementById('ip_port') || {}).textContent || ''; } catch (e) {}
  return '<div class="empty">' +
    '<h2>NO PHOTOS YET</h2>' +
    '<p>Your GTA camera shots land here. Follow the checklist, then snap in-game.</p>' +
    '<div class="empty-lan" id="empty_lan_copy" title="Tap to copy">' +
    '<div class="label">FIRST VISIT - OPEN ON YOUR PHONE</div>' +
    '<div class="ipport">' + escapeHtml(ipPort) + '</div>' +
    '<div class="hint">Tap to copy · same Wi-Fi as this PC · keep Copy above too</div>' +
    '</div>' +
    '<ol>' +
    '<li>Run <b>GroveLink Phone</b> / <b>START_GROVELINK</b> on the PC (keep the window open).</li>' +
    '<li>On your phone open <b>http://</b> + the address above (or use Copy).</li>' +
    '<li>In GTA press <b>K</b> → <b>Camera</b> → <b>Enter</b> or <b>Space</b>.</li>' +
    '<li>Phone and PC must be on the <b>same Wi-Fi</b>.</li>' +
    '<li>Text CJ from the sticky composer - he gets it in-game (INBOX / on-screen notify).</li>' +
    '</ol>' +
    '</div>';
}
var EMPTY_TODAY =
  '<div class="empty">' +
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
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;').replace(/'/g,'&#39;');
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

function loadLocalFavs() {
  try {
    var raw = localStorage.getItem(LS_FAV) || '[]';
    var arr = JSON.parse(raw);
    if (!arr || !arr.length) return {};
    var o = {};
    for (var i = 0; i < arr.length; i++) o[String(arr[i])] = true;
    return o;
  } catch (e) { return {}; }
}
function saveLocalFavs(map) {
  try {
    var arr = [];
    for (var k in map) { if (map[k]) arr.push(k); }
    localStorage.setItem(LS_FAV, JSON.stringify(arr));
  } catch (e) {}
}
var LOCAL_FAVS = loadLocalFavs();
function isFav(name) {
  if (!name) return false;
  if (LOCAL_FAVS[name]) return true;
  return false;
}
function mergeServerFavs(photos) {
  for (var i = 0; i < (photos || []).length; i++) {
    var p = photos[i];
    if (p && p.favorite && p.file) LOCAL_FAVS[p.file] = true;
  }
  saveLocalFavs(LOCAL_FAVS);
}
function toggleFavorite(name) {
  name = String(name || '');
  if (!name) return;
  var on = !isFav(name);
  LOCAL_FAVS[name] = on;
  if (!on) delete LOCAL_FAVS[name];
  saveLocalFavs(LOCAL_FAVS);
  renderFeed(LAST_PHOTOS);
  var x = new XMLHttpRequest();
  x.open('POST', '/favorite', true);
  x.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
  x.send('file=' + encodeURIComponent(name) + '&favorite=' + (on ? '1' : '0'));
}
function getChatReadTs() {
  try {
    var v = parseInt(localStorage.getItem(LS_CHAT_READ) || '0', 10);
    return isNaN(v) ? 0 : v;
  } catch (e) { return 0; }
}
function setChatReadTs(ts) {
  try { localStorage.setItem(LS_CHAT_READ, String(ts || Math.floor(Date.now()/1000))); } catch (e) {}
}
function countUnreadCj(inbox) {
  var readTs = getChatReadTs();
  var n = 0;
  for (var i = 0; i < (inbox || []).length; i++) {
    var m = inbox[i] || {};
    var isCj = (m.role === 'cj') || (m.side === 'cj') || ((m['from'] || '').toUpperCase() === 'CJ');
    if (!isCj) continue;
    var ts = parseInt(m.ts || m.time || 0, 10) || 0;
    if (ts > readTs) n++;
  }
  return n;
}
function updateChatBadge(inbox) {
  var n = countUnreadCj(inbox);
  var b = document.getElementById('chat_unread');
  if (!b) return;
  if (n > 0) {
    b.textContent = String(n);
    b.className = 'chatbadge show';
  } else {
    b.textContent = '0';
    b.className = 'chatbadge';
  }
}
function isChatMuted() {
  try { return localStorage.getItem(LS_MUTE) === '1'; } catch (e) { return false; }
}
function setChatMuted(on) {
  try { localStorage.setItem(LS_MUTE, on ? '1' : '0'); } catch (e) {}
  paintMuteBtn();
}
function paintMuteBtn() {
  var b = document.getElementById('chat_mute_btn');
  if (!b) return;
  var on = isChatMuted();
  b.textContent = on ? 'Unmute alerts' : 'Mute alerts';
  b.className = on ? 'on' : '';
}
function applyDensity(mode) {
  mode = (mode === 'bright') ? 'bright' : 'dark';
  try { localStorage.setItem(LS_DENSITY, mode); } catch (e) {}
  var cls = (document.body.className || ''); var _p=cls.split(' '); var _o=[]; for(var _i=0;_i<_p.length;_i++){ if(_p[_i] && _p[_i].indexOf('density-')!==0) _o.push(_p[_i]); } cls=_o.join(' ').trim();
  document.body.className = (cls + ' density-' + mode).trim();
  var d = document.getElementById('theme_dark');
  var b = document.getElementById('theme_bright');
  if (d) d.className = (mode === 'dark') ? 'on' : '';
  if (b) b.className = (mode === 'bright') ? 'on' : '';
}
function maybeNotifyCj(inbox) {
  try {
    if (isChatMuted()) return;
    if (!('Notification' in window)) return;
    if (Notification.permission !== 'granted') return;
    var readTs = getChatReadTs();
    var newest = null;
    for (var i = 0; i < (inbox || []).length; i++) {
      var m = inbox[i] || {};
      var isCj = (m.role === 'cj') || (m.side === 'cj') || ((m['from'] || '').toUpperCase() === 'CJ');
      if (!isCj) continue;
      var ts = parseInt(m.ts || m.time || 0, 10) || 0;
      if (ts > readTs && (!newest || ts > (parseInt(newest.ts || 0, 10) || 0))) newest = m;
    }
    if (!newest) return;
    var key = 'gl_notif_' + (newest.ts || '') + '_' + (newest.msg || '');
    if (sessionStorage.getItem(key)) return;
    sessionStorage.setItem(key, '1');
    new Notification('CJ replied', { body: String(newest.msg || 'New reply').slice(0, 80), tag: 'grovelink-cj' });
  } catch (e) { /* fail soft on HTTP LAN / insecure contexts */ }
}
function paintHud(hud) {
  LAST_HUD = hud || null;
  var strip = document.getElementById('hud_strip');
  var tstrip = document.getElementById('time_strip');
  if (!hud) {
    if (strip) strip.className = 'hudstrip hidden';
    if (tstrip) tstrip.className = 'timestrip hidden';
    return;
  }
  var has = (hud.zone || hud.wanted > 0 || hud.money !== 0 || hud.spectate || (typeof hud.hour === 'number' && hud.hour >= 0));
  if (strip) {
    strip.className = has ? 'hudstrip' : 'hudstrip hidden';
    var w = document.getElementById('hud_wanted');
    var m = document.getElementById('hud_money');
    var z = document.getElementById('hud_zone');
    var s = document.getElementById('hud_spec');
    if (w) w.textContent = (hud.wanted > 0) ? ('★'.repeat(Math.min(6, hud.wanted))) : '0';
    if (m) {
      try { m.textContent = Number(hud.money || 0).toLocaleString(); }
      catch (e) { m.textContent = String(hud.money || 0); }
    }
    if (z) z.textContent = hud.zone || '-';
    if (s) s.textContent = hud.spectate ? 'ON' : 'off';
  }
  if (tstrip) {
    var hour = (typeof hud.hour === 'number') ? hud.hour : -1;
    if (hour >= 0 && hour <= 23) {
      tstrip.className = 'timestrip';
      var hh = (hour < 10 ? '0' : '') + hour + ':00';
      var el = document.getElementById('hud_hour');
      if (el) el.textContent = hh + ' (in-game)';
    } else {
      tstrip.className = 'timestrip hidden';
    }
  }
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

function shareUrl(url, title) {
  url = url || (document.getElementById('lan_url').textContent || window.location.href);
  title = title || 'GroveLink';
  if (navigator.share) {
    navigator.share({ title: title, url: url, text: title + ' - ' + url }).catch(function(){
      copyText(url, null);
      flashOk('Link copied');
    });
  } else {
    copyText(url, null);
    flashOk('Link copied');
  }
}
function flashOk(msg) {
  var okEl = document.getElementById('ok');
  if (!okEl) return;
  okEl.textContent = msg || '';
  setTimeout(function(){ okEl.textContent = ''; }, 2800);
}
function showToast(msg) {
  try {
    var t = document.getElementById('toast');
    if (!t) return;
    t.textContent = msg || '';
    t.className = 'toast show';
    setTimeout(function(){ t.className = 'toast'; }, 3000);
  } catch (e) { /* fail soft */ }
}
function loadNick() {
  try {
    var n = (localStorage.getItem(LS_NICK) || '').trim();
    var el = document.getElementById('from_name');
    if (el) el.value = n || 'REAL PHONE';
  } catch (e) {}
}
function saveNick() {
  try {
    var el = document.getElementById('from_name');
    var n = (el && el.value || '').trim();
    if (!n) n = 'REAL PHONE';
    if (el) el.value = n;
    localStorage.setItem(LS_NICK, n);
  } catch (e) {}
}
function maybeWantedToast(hud) {
  try {
    if (!hud) return;
    var w = parseInt(hud.wanted || 0, 10) || 0;
    if (LAST_WANTED >= 0 && w > LAST_WANTED) {
      showToast('WANTED ★ increased');
    }
    LAST_WANTED = w;
  } catch (e) { /* fail soft */ }
}
function paintWatching(n) {
  n = parseInt(n, 10) || 0;
  var qa = document.getElementById('qa_watching');
  var note = document.getElementById('watching_note');
  var label = n + ' watching';
  if (qa) {
    qa.textContent = label;
    qa.style.display = (n > 0) ? '' : 'none';
  }
  if (note) {
    if (n > 0) {
      note.textContent = n + ' watching LIVE SPECTATE';
      note.className = 'watching show';
    } else {
      note.textContent = '';
      note.className = 'watching';
    }
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
  saveNick();
  var frm = (document.getElementById('from_name').value || 'REAL PHONE').trim() || 'REAL PHONE';
  if (!frm) frm = 'REAL PHONE';
  var body = 'msg=' + encodeURIComponent(msg) + '&from=' + encodeURIComponent(frm);
  var x = new XMLHttpRequest();
  x.open('POST', '/send', true);
  x.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
  x.onreadystatechange = function() {
    if (x.readyState === 4) {
      var okEl = document.getElementById('ok');
      if (x.status === 200) {
        okEl.textContent = 'Delivered to CJ - open INBOX (or watch on-screen SMS notify).';
        document.getElementById('msg').value = '';
        poll();
      } else if (x.status === 429) {
        var detail = 'Slow down — 1 text every 3 seconds.';
        try { var jr = JSON.parse(x.responseText); if (jr && jr.detail) detail = jr.detail; } catch (e429) {}
        okEl.textContent = detail;
      } else {
        okEl.textContent = 'Send failed.';
      }
      setTimeout(function(){ okEl.textContent = ''; }, 3500);
    }
  };
  x.send(body);
}
function saveCaption(name, val) {
  var body = 'file=' + encodeURIComponent(name) + '&caption=' + encodeURIComponent(val || '');
  var x = new XMLHttpRequest();
  x.open('POST', '/caption', true);
  x.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
  x.onreadystatechange = function() {
    if (x.readyState === 4) {
      if (x.status === 200) {
        flashOk('Caption saved');
        poll();
      } else {
        flashOk('Caption save failed');
      }
    }
  };
  x.send(body);
}

function saveComment(name, val) {
  var body = 'file=' + encodeURIComponent(name) + '&comment=' + encodeURIComponent(val || '');
  var x = new XMLHttpRequest();
  x.open('POST', '/comment', true);
  x.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
  x.onreadystatechange = function() {
    if (x.readyState === 4) {
      if (x.status === 200) {
        flashOk('Comment saved');
        poll();
      } else {
        flashOk('Comment save failed');
      }
    }
  };
  x.send(body);
}
var PENDING_NEWS = '';
function newsDlgCancel(ev) {
  if (ev) ev.stopPropagation();
  PENDING_NEWS = '';
  var dlg = document.getElementById('news_dlg');
  if (dlg) dlg.className = '';
}
function newsDlgFile() {
  var name = PENDING_NEWS;
  var sel = document.getElementById('news_loc_sel');
  var txt = document.getElementById('news_loc_txt');
  var loc = '';
  if (txt && (txt.value || '').trim()) loc = (txt.value || '').trim();
  else if (sel && sel.value) loc = sel.value;
  newsDlgCancel();
  if (!name) return;
  doBreakingNews(name, loc);
}
function breakingNews(name) {
  if (!name) return;
  PENDING_NEWS = name;
  var sel = document.getElementById('news_loc_sel');
  var txt = document.getElementById('news_loc_txt');
  if (sel) sel.value = '';
  if (txt) txt.value = '';
  var dlg = document.getElementById('news_dlg');
  if (dlg) dlg.className = 'show';
}
function doBreakingNews(name, location) {
  if (!name) return;
  var capEl = document.getElementById('cap_' + cssId(name));
  var cap = capEl ? (capEl.value || '') : '';
  var body = 'file=' + encodeURIComponent(name) + '&caption=' + encodeURIComponent(cap);
  if (location) body += '&location=' + encodeURIComponent(location);
  var x = new XMLHttpRequest();
  x.open('POST', '/news', true);
  x.setRequestHeader('Content-Type', 'application/x-www-form-urlencoded');
  x.onreadystatechange = function() {
    if (x.readyState === 4) {
      if (x.status === 200) {
        try {
          var j = JSON.parse(x.responseText);
          if (j.id) {
            flashOk('News filed - opening Herald…');
            setTimeout(function(){ window.location.href = '/news/' + j.id; }, 400);
            return;
          }
        } catch (e) {}
        flashOk('News filed');
        poll();
      } else {
        flashOk('Breaking News failed');
      }
    }
  };
  x.send(body);
}
function cssId(name) {
  return String(name).replace(/[^a-zA-Z0-9]/g, '_');
}
function sharePhoto(name) {
  var url = window.location.origin + '/photo/' + name;
  shareUrl(url, 'GroveLink shot');
}

function setFilter(f) {
  FILTER = f;
  if (f !== 'places') PLACE_FILTER = '';
  var all = document.getElementById('tab_all');
  var today = document.getElementById('tab_today');
  var fav = document.getElementById('tab_fav');
  var place = document.getElementById('tab_place');
  if (all) all.className = (f === 'all') ? 'tab on' : 'tab';
  if (today) today.className = (f === 'today') ? 'tab on' : 'tab';
  if (fav) fav.className = (f === 'favorites') ? 'tab on' : 'tab';
  if (place) place.className = (f === 'places') ? 'tab on' : 'tab';
  renderFeed(LAST_PHOTOS);
}
function setPlaceFilter(place) {
  PLACE_FILTER = place || '';
  FILTER = 'places';
  setFilter('places');
}

function photoCard(p, isHero) {
  var name = p.file || p;
  var when = p.when || '';
  var mtime = parseInt(p.mtime || 0, 10) || 0;
  var sizeH = p.size_h || '';
  var cap = p.caption || '';
  var lastVisit = getLastVisit();
  var isNew = mtime > lastVisit;
  var href = '/photo/' + name;
  var safe = String(name).replace(/'/g, '');
  var cid = cssId(name);
  var cls = isHero ? 'hero' : 'shot';
  if (isNew) cls += ' unread';
  var html = '<div class="' + cls + '">';
  if (isNew) html += '<div class="badge">NEW</div>';
  html += '<a class="imgwrap" href="' + href + '" target="_blank" rel="noopener" onclick="openLb(\\'' + href + '\\'); return false;">';
  html += '<img src="' + href + '" alt="shot">';
  html += '</a>';
  var loc = p.location || '';
  var metaBits = [];
  if (when) metaBits.push(when);
  if (sizeH) metaBits.push(sizeH);
  metaBits.push(name);
  html += '<div class="meta"><span class="grow">' + escapeHtml(metaBits.join(' · ')) +
          (loc ? (' <span class="locbadge-mini">📍 ' + escapeHtml(loc) + '</span>') : '') +
          ' · <a href="' + href + '" target="_blank" rel="noopener">full size</a></span></div>';
  html += '<div class="caprow"><input id="cap_' + cid + '" type="text" maxlength="200" placeholder="Optional caption…" value="' + escapeHtml(cap) + '">';
  html += '<button type="button" class="capbtn" onclick="saveCaption(\\'' + safe + '\\', document.getElementById(\\'' + 'cap_' + cid + '\\').value)">Save</button></div>';
  var cmt = p.comment || '';
  html += '<div class="commentshow" id="cmtshow_' + cid + '">' + (cmt ? escapeHtml(cmt) : '') + '</div>';
  html += '<div class="commentrow"><input id="cmt_' + cid + '" type="text" maxlength="140" placeholder="Short comment…" value="' + escapeHtml(cmt) + '">';
  html += '<button type="button" class="capbtn" onclick="saveComment(\\'' + safe + '\\', document.getElementById(\\'' + 'cmt_' + cid + '\\').value)">Comment</button></div>';
  html += '<div class="btns">';
  html += '<button type="button" class="newsbtn" onclick="breakingNews(\\'' + safe + '\\')">Breaking News</button>';
  var favOn = isFav(name) || !!p.favorite;
  html += '<button type="button" class="favbtn' + (favOn ? ' on' : '') + '" onclick="toggleFavorite(\\'' + safe + '\\')">' + (favOn ? '★ Fav' : '☆ Fav') + '</button>';
  html += '<button type="button" class="sharebtn" onclick="sharePhoto(\\'' + safe + '\\')">Share</button>';
  html += '<button type="button" class="delbtn" onclick="deletePhoto(\\'' + safe + '\\')">Delete</button>';
  html += '</div></div>';
  return { html: html, isNew: isNew };
}

function renderPinned(pinned) {
  var wrap = document.getElementById('chat_pin');
  var body = document.getElementById('chat_pin_body');
  if (!wrap || !body) return;
  PINNED_ID = (pinned && pinned.id) ? String(pinned.id) : '';
  if (!pinned || !pinned.msg) {
    wrap.className = 'chatpin';
    body.innerHTML = '';
    return;
  }
  var who = pinned.from || 'REAL PHONE';
  body.innerHTML = '<strong>' + escapeHtml(who) + '</strong>: ' + escapeHtml(pinned.msg || '') +
    ' <button type="button" class="pinbtn" onclick="pinChat(\'\')">Unpin</button>';
  wrap.className = 'chatpin show';
}
function renderChat(inbox, pinned) {
  LAST_CHAT = inbox || [];
  var box = document.getElementById('chat_thread');
  if (!box) return;
  var list = inbox || [];
  LAST_CHAT = list;
  if (typeof pinned !== 'undefined') {
    renderPinned(pinned);
  }
  if (!list.length) {
    box.innerHTML = '<div class="chatempty">Send a message below - delivered texts show here. CJ replies appear on the right.</div>';
    return;
  }
  var html = '';
  for (var i = 0; i < list.length && i < 12; i++) {
    var m = list[i];
    var text = typeof m === 'string' ? m : (m.msg || '');
    var who = (typeof m === 'object' && m.from) ? m.from : 'REAL PHONE';
    var when = (typeof m === 'object' && m.when) ? m.when : '';
    var role = (typeof m === 'object' && (m.role || m.side)) ? String(m.role || m.side).toLowerCase() : '';
    var isCj = role === 'cj' || String(who).toUpperCase() === 'CJ';
    var mid = (typeof m === 'object' && m.id) ? String(m.id) : '';
    var cls = isCj ? 'chatmsg cj' : 'chatmsg visitor';
    if (mid && mid === PINNED_ID) cls += ' pinned';
    html += '<div class="' + cls + '" data-id="' + escapeHtml(mid) + '"><div class="who">' + escapeHtml(who) + (when ? ' · ' + escapeHtml(when) : '') + '</div>';
    html += escapeHtml(text);
    if (isCj) {
      html += '<div class="deliv">CJ replied</div>';
    } else {
      html += '<div class="deliv">Delivered to CJ</div>';
    }
    if (mid) {
      var rx = (typeof m === 'object' && m.reactions) ? m.reactions : {};
      var u = parseInt(rx['👍'] || 0, 10) || 0;
      var l = parseInt(rx['😂'] || 0, 10) || 0;
      var f = parseInt(rx['🔥'] || 0, 10) || 0;
      var safeId = String(mid).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
      html += '<div class="reacts">';
      html += '<button type="button" onclick="reactChat(\'' + safeId + '\',\'up\')">👍 ' + u + '</button>';
      html += '<button type="button" onclick="reactChat(\'' + safeId + '\',\'laugh\')">😂 ' + l + '</button>';
      html += '<button type="button" onclick="reactChat(\'' + safeId + '\',\'fire\')">🔥 ' + f + '</button>';
      html += '<button type="button" class="pinbtn" onclick="pinChat(\'' + safeId + '\')">' + (mid === PINNED_ID ? 'Unpin' : 'Pin') + '</button>';
      html += '</div>';
    }
    html += '</div>';
  }
  box.innerHTML = html;
}
function reactChat(id, reaction) {
  var x = new XMLHttpRequest();
  x.open('POST', '/react', true);
  x.setRequestHeader('Content-Type', 'application/json');
  x.onload = function() { try { refreshNow(); } catch (e) {} };
  x.send(JSON.stringify({id: id, reaction: reaction}));
}
function pinChat(id) {
  var x = new XMLHttpRequest();
  x.open('POST', '/pin', true);
  x.setRequestHeader('Content-Type', 'application/json');
  x.onload = function() { try { refreshNow(); } catch (e) {} };
  x.send(JSON.stringify(id ? {id: id} : {clear: 1}));
}

function renderMoments(photos) {
  var reel = document.getElementById('moments_reel');
  if (!reel) return;
  var today0 = startOfTodaySec();
  var todays = [];
  var list = photos || [];
  for (var i = 0; i < list.length; i++) {
    var mt = parseInt(list[i].mtime || 0, 10) || 0;
    if (mt >= today0) todays.push(list[i]);
  }
  if (!todays.length || FILTER === 'places') {
    reel.className = 'moments';
    reel.innerHTML = '';
    return;
  }
  var html = '<span class="mlab">TODAY</span><div class="mrow">';
  for (var j = 0; j < todays.length && j < 24; j++) {
    var p = todays[j];
    var name = p.file || '';
    var href = '/photo/' + name;
    var safe = String(name).replace(/'/g, "\\'");
    html += '<div class="mcell" onclick="openLb(\'' + href + '\')" title="' + escapeHtml(name) + '">';
    html += '<div class="mring"><img src="' + href + '" alt=""></div>';
    html += '<div class="mlabel">' + escapeHtml((p.when || 'today').split(' ').slice(-2).join(' ') || 'today') + '</div>';
    html += '</div>';
  }
  html += '</div>';
  reel.innerHTML = html;
  reel.className = 'moments show';
}
function renderPlacesList() {
  var feed = document.getElementById('feed');
  var places = LAST_PLACES || [];
  if (!places.length) {
    // derive from photos client-side
    var counts = {};
    for (var i = 0; i < (LAST_PHOTOS || []).length; i++) {
      var loc = (LAST_PHOTOS[i].location || '').trim();
      if (loc) counts[loc] = (counts[loc] || 0) + 1;
    }
    places = [];
    for (var k in counts) {
      if (counts.hasOwnProperty(k)) places.push({place: k, count: counts[k]});
    }
    places.sort(function(a,b){ return (b.count - a.count) || String(a.place).localeCompare(b.place); });
  }
  if (!places.length) {
    feed.innerHTML = '<div class="empty"><h2>NO PLACES YET</h2><p>File Breaking News with a location, or put <b>#Grove Street</b> / <b>loc:Idlewood</b> in a caption.</p></div>';
    return;
  }
  var html = '<div class="sectionlab">BY PLACE</div><div class="placelist">';
  for (var p = 0; p < places.length; p++) {
    var pl = places[p].place;
    var cn = places[p].count;
    var safe = String(pl).replace(/\\/g, '\\\\').replace(/'/g, "\\'");
    html += '<div class="placeitem" onclick="setPlaceFilter(\'' + safe + '\')"><span>📍 ' +
            escapeHtml(pl) + '</span><span class="pc">' + cn + '</span></div>';
  }
  html += '</div>';
  feed.innerHTML = html;
}
function renderFeed(photos) {
  var feed = document.getElementById('feed');
  var unread = 0;
  var today0 = startOfTodaySec();
  var list = photos || [];
  renderMoments(photos);
  if (FILTER === 'places' && !PLACE_FILTER) {
    document.getElementById('unread_count').textContent = '0';
    renderPlacesList();
    return;
  }
  if (FILTER === 'today') {
    var filtered = [];
    for (var j = 0; j < list.length; j++) {
      var mt = parseInt(list[j].mtime || 0, 10) || 0;
      if (mt >= today0) filtered.push(list[j]);
    }
    list = filtered;
  }
  if (FILTER === 'favorites') {
    var filteredF = [];
    for (var jf = 0; jf < list.length; jf++) {
      var pf = list[jf];
      if (isFav(pf.file) || !!pf.favorite) filteredF.push(pf);
    }
    list = filteredF;
  }
  if (FILTER === 'places' && PLACE_FILTER) {
    var filteredP = [];
    for (var jp = 0; jp < list.length; jp++) {
      if ((list[jp].location || '') === PLACE_FILTER) filteredP.push(list[jp]);
    }
    list = filteredP;
  }
  if (SEARCH_Q) {
    var q = SEARCH_Q.toLowerCase();
    var filtered2 = [];
    for (var k = 0; k < list.length; k++) {
      var nm = String(list[k].file || list[k] || '').toLowerCase();
      var cp = String(list[k].caption || '').toLowerCase();
      var lc = String(list[k].location || '').toLowerCase();
      if (nm.indexOf(q) >= 0 || cp.indexOf(q) >= 0 || lc.indexOf(q) >= 0) filtered2.push(list[k]);
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
      feed.innerHTML = '<div class="empty"><h2>NO MATCHES</h2><p>No filenames match <b>' + escapeHtml(SEARCH_Q) + '</b>. Clear the search box.</p></div>';
    } else if (FILTER === 'favorites') {
      feed.innerHTML = '<div class="empty"><h2>NO FAVORITES</h2><p>Tap ★ on a shot to star it. Favorites sync in this browser + optional bridge JSON.</p></div>';
    } else if (FILTER === 'places') {
      feed.innerHTML = '<button type="button" class="placeback" onclick="setPlaceFilter(\'\')">← All places</button><div class="empty"><h2>NO SHOTS HERE</h2><p>No photos tagged <b>' + escapeHtml(PLACE_FILTER) + '</b>.</p></div>';
    } else {
      feed.innerHTML = EMPTY_TODAY;
    }
    return;
  }
  var lastVisit = getLastVisit();
  for (var u = 0; u < list.length; u++) {
    var mt2 = parseInt(list[u].mtime || 0, 10) || 0;
    if (mt2 > lastVisit) unread++;
  }
  var html = '';
  if (FILTER === 'places' && PLACE_FILTER) {
    html += '<button type="button" class="placeback" onclick="setPlaceFilter(\'\')">← All places</button>';
    html += '<div class="sectionlab">📍 ' + escapeHtml(PLACE_FILTER) + '</div>';
  }
  var hero = list[0];
  var card0 = photoCard(hero, true);
  html += '<div class="sectionlab">LATEST</div>' + card0.html;
  if (list.length > 1) {
    html += '<div class="sectionlab">FEED</div><div class="grid">';
    for (var i = 1; i < list.length && i < 40; i++) {
      html += photoCard(list[i], false).html;
    }
    html += '</div>';
  }
  document.getElementById('unread_count').textContent = String(unread);
  feed.innerHTML = html;
}

function paint(data) {
  var count = document.getElementById('count');
  var photos = data.photos || [];
  LAST_PHOTOS = photos;
  var nCount = (typeof data.count === 'number') ? data.count : photos.length;
  count.textContent = nCount;
  setCountActions(nCount, data.latest || (photos[0] && (photos[0].file || photos[0])) || '');
  var lr = data.last_refresh_human || data.last_refresh || '-';
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
  mergeServerFavs(photos);
  if (data.favorites && data.favorites.length) {
    for (var fi = 0; fi < data.favorites.length; fi++) LOCAL_FAVS[data.favorites[fi]] = true;
    saveLocalFavs(LOCAL_FAVS);
  }
  paintHud(data.hud || null);
  maybeWantedToast(data.hud || null);
  paintWatching(data.watching);
  paintViewers(data.viewers || []);
  paintPoll(data.poll || null);
  paintRequests(data.requests || []);
  LAST_PLACES = data.places || [];
  renderChat(data.inbox || [], data.pinned || null);
  updateChatBadge(data.inbox || []);
  var upEl = document.getElementById('uptime_val');
  if (upEl) upEl.textContent = data.uptime_human || (data.uptime_sec != null ? (data.uptime_sec + 's') : '-');
  var stEl = document.getElementById('streak_val');
  if (stEl) stEl.textContent = String(parseInt(data.streak || 0, 10) || 0);
  maybeNotifyCj(data.inbox || []);
  if (data.poll_ms && data.spectate_on) {
    var hot = Math.min(parseInt(data.poll_ms, 10) || 2000, 1000);
    if (hot !== POLL_MS && data.spectate_on) { /* phone page keeps poll_ms; spectate page hotter */ }
  }
  if (data.poll_ms) {
    var pm = parseInt(data.poll_ms, 10);
    if (pm >= 500 && pm !== POLL_MS) POLL_MS = pm;
  }
  renderFeed(photos);
}
function setCountActions(n, latest) {
  var has = (parseInt(n, 10) || 0) > 0;
  var dl = document.getElementById('dl_latest');
  var ex = document.getElementById('export_zip');
  var cl = document.getElementById('clear_all');
  if (dl) {
    if (has && latest) {
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
  }
  if (ex) {
    if (has) {
      ex.href = '/export.zip';
      ex.removeAttribute('disabled');
      ex.style.opacity = '1';
      ex.style.pointerEvents = 'auto';
    } else {
      ex.href = '#';
      ex.setAttribute('disabled', 'disabled');
      ex.style.opacity = '0.4';
      ex.style.pointerEvents = 'none';
    }
  }
  if (cl) {
    if (has) {
      cl.removeAttribute('disabled');
    } else {
      cl.setAttribute('disabled', 'disabled');
    }
  }
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
function refreshNow() { poll(); }
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
      setOfflineUI('Bridge offline - run START_GROVELINK');
    }
  };
  x.ontimeout = function() { setOfflineUI('Bridge offline - run START_GROVELINK'); };
  x.onerror = function() { setOfflineUI('Bridge offline - run START_GROVELINK'); };
  try { x.send(); } catch (e) { setOfflineUI('Bridge offline - run START_GROVELINK'); }
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
document.getElementById('share_page').onclick = function() {
  shareUrl(document.getElementById('lan_url').textContent, 'GroveLink');
};
document.getElementById('tab_all').onclick = function() { setFilter('all'); };
document.getElementById('tab_today').onclick = function() { setFilter('today'); };
(function(){ var t=document.getElementById('tab_fav'); if(t) t.onclick=function(){ setFilter('favorites'); }; })();
(function(){ var t=document.getElementById('tab_place'); if(t) t.onclick=function(){ PLACE_FILTER=''; setFilter('places'); }; })();
(function(){
  var el = document.getElementById('from_name');
  if (!el) return;
  el.onchange = saveNick;
  el.onblur = saveNick;
})();
loadNick();
(function() {
  var btn = document.getElementById('tab_sort');
  if (!btn) return;
  btn.onclick = function() {
    SORT_ORDER = (SORT_ORDER === 'newest') ? 'oldest' : 'newest';
    btn.setAttribute('data-sort', SORT_ORDER);
    btn.textContent = (SORT_ORDER === 'newest') ? 'Newest' : 'Oldest';
    btn.className = 'tab';
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
document.getElementById('clear_all').onclick = function() {
  if (this.disabled) return;
  if (!(LAST_PHOTOS && LAST_PHOTOS.length)) return;
  clearAllPhotos();
};
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
  flashOk('Marked all as read.');
};
(function(){
  var qaCam = document.getElementById('qa_camera');
  if (qaCam) qaCam.onclick = function(){
    flashOk('In GTA: press K → Camera → Enter/Space. Photos appear here (gallery only - not Herald).');
  };
  var qaText = document.getElementById('qa_text');
  if (qaText) qaText.onclick = function(){
    var m = document.getElementById('msg');
    if (m) { m.focus(); try { m.scrollIntoView({behavior:'smooth', block:'center'}); } catch(e) { m.scrollIntoView(); } }
  };
  var cmr = document.getElementById('chat_mark_read');
  if (cmr) cmr.onclick = function(){
    setChatReadTs(Math.floor(Date.now()/1000));
    updateChatBadge(LAST_CHAT);
    flashOk('Chat marked read.');
  };
  var cnb = document.getElementById('chat_notify_btn');
  if (cnb) cnb.onclick = function(){
    if (isChatMuted()) { setChatMuted(false); }
    if (!('Notification' in window)) {
      flashOk('Notifications not supported in this browser.');
      return;
    }
    try {
      Notification.requestPermission().then(function(p){
        flashOk(p === 'granted' ? 'CJ alerts enabled (when browser allows).' : 'Permission: ' + p + ' (fails soft on HTTP LAN).');
      }).catch(function(){ flashOk('Could not request notification permission.'); });
    } catch (e) {
      flashOk('Notifications unavailable (try HTTPS or supported browser).');
    }
  };
  var cmb = document.getElementById('chat_mute_btn');
  if (cmb) cmb.onclick = function(){
    var next = !isChatMuted();
    setChatMuted(next);
    flashOk(next ? 'Chat notifications muted.' : 'Chat notifications unmuted.');
  };
  paintMuteBtn();
  var td = document.getElementById('theme_dark');
  var tb = document.getElementById('theme_bright');
  if (td) td.onclick = function(){ applyDensity('dark'); flashOk('Dark street theme'); };
  if (tb) tb.onclick = function(){ applyDensity('bright'); flashOk('Bright green theme'); };
  try {
    var dens = localStorage.getItem(LS_DENSITY) || 'dark';
    applyDensity(dens === 'bright' ? 'bright' : 'dark');
  } catch (e3) { applyDensity('dark'); }
})();

(function(){
  setMode(getMode());
  var mv = document.getElementById('mode_viewer');
  var mh = document.getElementById('mode_host');
  if (mv) mv.onclick = function(){ setMode('viewer'); flashOk('Viewer mode'); };
  if (mh) mh.onclick = function(){ setMode('host'); flashOk('Host mode — local only (localStorage)'); };
  var reqbar = document.getElementById('reqbar');
  if (reqbar) {
    var rbtns = reqbar.querySelectorAll('button[data-kind]');
    for (var i = 0; i < rbtns.length; i++) {
      rbtns[i].onclick = (function(b){
        return function(){ sendRequest(b.getAttribute('data-kind')); };
      })(rbtns[i]);
    }
  }
  var bb = document.getElementById('bcast_btn');
  if (bb) bb.onclick = doBroadcast;
  var pc = document.getElementById('poll_create');
  if (pc) pc.onclick = doCreatePoll;
  var pcl = document.getElementById('poll_close');
  if (pcl) pcl.onclick = doClosePoll;
  var rc = document.getElementById('req_clear');
  if (rc) rc.onclick = function(){
    postForm('/request', 'action=clear', function(st, j){
      flashOk((j && j.detail) || 'Cleared');
      poll();
    });
  };
})();

// Light pull-to-refresh on feed
(function(){
  var startY = 0;
  var pulling = false;
  document.addEventListener('touchstart', function(ev){
    if (window.scrollY <= 0 && ev.touches && ev.touches[0]) {
      startY = ev.touches[0].clientY; pulling = true;
    } else { pulling = false; }
  }, {passive:true});
  document.addEventListener('touchend', function(ev){
    if (!pulling) return;
    pulling = false;
    try {
      var y = (ev.changedTouches && ev.changedTouches[0]) ? ev.changedTouches[0].clientY : 0;
      if (y - startY > 70) { poll(); flashOk('Refreshed.'); }
    } catch (e) {}
  }, {passive:true});
})();
document.getElementById('f').onsubmit = function(ev) {
  ev.preventDefault();
  sendMsg(document.getElementById('msg').value);
};
if (!getLastVisit()) {
  try { /* leave 0 so existing shots show NEW on first open */ } catch (e) {}
}
document.getElementById('confirm_yes').onclick = function(ev){ if(ev)ev.stopPropagation(); confirmYes(); };
document.getElementById('confirm_no').onclick = function(ev){ if(ev)ev.stopPropagation(); confirmCancel(ev); };
(function(){
  var go = document.getElementById('news_go');
  var cancel = document.getElementById('news_cancel');
  if (go) go.onclick = function(ev){ if(ev)ev.stopPropagation(); newsDlgFile(); };
  if (cancel) cancel.onclick = function(ev){ if(ev)ev.stopPropagation(); newsDlgCancel(ev); };
})();
function toggleHelpDetail(force) {
  var d = document.getElementById('help_detail');
  var t = document.getElementById('help_toggle');
  if (!d) return;
  var open;
  if (typeof force === 'boolean') open = force;
  else open = !/\bshow\b/.test(d.className || '');
  d.className = open ? 'help-detail show' : 'help-detail';
  if (t) t.textContent = open ? 'less' : 'more';
}
(function() {
  var t = document.getElementById('help_toggle');
  if (t) t.onclick = function() { toggleHelpDetail(); };
})();
document.addEventListener('keydown', function(ev) {
  var tag = (ev.target && ev.target.tagName) ? ev.target.tagName.toUpperCase() : '';
  var typing = (tag === 'INPUT' || tag === 'TEXTAREA');
  var key = ev.key || '';
  var code = ev.keyCode || ev.which || 0;
  if (code === 27 || key === 'Escape') {
    var lb = document.getElementById('lightbox');
    if (lb && lb.className === 'show') { closeLb(ev); return; }
    var nd = document.getElementById('news_dlg');
    if (nd && nd.className === 'show') { newsDlgCancel(ev); return; }
    var dlg = document.getElementById('confirm_dlg');
    if (dlg && dlg.className === 'show') { confirmCancel(ev); return; }
  }
  if (typing) return;
  if (key === '?' || (ev.shiftKey && code === 191)) {
    toggleHelpDetail();
    if (ev.preventDefault) ev.preventDefault();
    return;
  }
  if (key === '/' || code === 191) {
    var s = document.getElementById('search');
    if (s) { s.focus(); if (ev.preventDefault) ev.preventDefault(); }
  }
});
document.getElementById('feed').innerHTML = emptyHtml();
bindEmptyLanCopy();
setCountActions(0, '');
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
    """No QR dependency - large tap-to-copy IP:port + sms-style note."""
    ip = STATE.get("ip", "127.0.0.1")
    port = STATE.get("port", 8088)
    lan = "http://%s:%s" % (ip, port)
    ip_port = "%s:%s" % (ip, port)
    sms_body = "GroveLink phone page: %s" % lan
    # Keep HTML simple, stdlib only, no SVG QR
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1\">"
        "<title>GroveLink - share URL</title>"
        "<style>"
        "body{margin:0;background:#070b08;color:#d7ffd0;font-family:Arial,sans-serif;}"
        ".box{max-width:440px;margin:40px auto;padding:20px;text-align:center;}"
        "h1{color:#2cff6a;letter-spacing:2px;font-size:18px;}"
        ".ip{font-size:28px;font-weight:bold;color:#2cff6a;margin:24px 0;padding:20px;"
        "border:2px solid #2cff6a;cursor:pointer;word-break:break-all;}"
        "a{color:#2cff6a;} p{color:#7aaa7a;line-height:1.5;font-size:13px;}"
        "</style></head><body><div class=\"box\">"
        "<h1>GROVELINK</h1>"
        "<p>No QR code library - tap the address to copy, then open it on your phone "
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



def render_recap_html():
    """Simple HTML session recap for today (photos / news / chat / streak / top place)."""
    data = session_recap_data()
    ver = _esc(data.get("version") or "unknown")
    top = data.get("top_location") or ""
    top_s = _esc(top) if top else "(none yet)"
    top_c = int(data.get("top_location_count") or 0)
    up = _esc(data.get("uptime_human") or "0s")
    streak = int(data.get("streak") or 0)
    top_extra = ""
    if top:
        top_extra = ' <span style="color:#7aaa7a;font-size:14px">&times;%d</span>' % top_c
    body = (
        '<!DOCTYPE html><html><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<meta name="theme-color" content="#041006">'
        '<title>GroveLink Session Recap</title>'
        '<style>'
        'body{margin:0;background:#050805;color:#d7ffd0;font-family:system-ui,-apple-system,Segoe UI,Arial,sans-serif;padding:24px 18px 48px}'
        '.wrap{max-width:560px;margin:0 auto}'
        'h1{font-size:20px;letter-spacing:2px;color:#2cff6a;margin:0 0 6px;font-weight:800}'
        'p.sub{color:#8bbb8b;font-size:13px;margin:0 0 22px;line-height:1.5}'
        '.grid{display:grid;grid-template-columns:1fr 1fr;gap:12px}'
        '.card{background:#0b120e;border:1px solid #1f5a2a;border-radius:8px;padding:16px}'
        '.card .k{font-size:10px;letter-spacing:1.5px;color:#7aaa7a;text-transform:uppercase}'
        '.card .v{font-size:30px;font-weight:800;color:#2cff6a;margin-top:8px;letter-spacing:0.5px}'
        '.card.wide{grid-column:1/-1}'
        '.card.accent{border-color:#2cff6a;background:#0e1a12}'
        'a.back{display:inline-block;margin-top:20px;margin-right:12px;color:#2cff6a;font-weight:bold;text-decoration:none;'
        'padding:10px 0;font-size:13px}'
        '.foot{margin-top:20px;font-size:12px;color:#7aaa7a;line-height:1.5}'
        '@media(max-width:420px){.grid{grid-template-columns:1fr}}'
        '</style></head><body><div class="wrap">'
        '<h1>SESSION RECAP</h1>'
        '<p class="sub">Today on this bridge · GroveLink __VER__ · overview of photos, Herald, chat, and streak</p>'
        '<div class="grid">'
        '<div class="card"><div class="k">PHOTOS TODAY</div><div class="v">__P__</div></div>'
        '<div class="card"><div class="k">NEWS TODAY</div><div class="v">__N__</div></div>'
        '<div class="card"><div class="k">CHAT TODAY</div><div class="v">__C__</div></div>'
        '<div class="card accent"><div class="k">PHOTO STREAK</div><div class="v">__S__</div></div>'
        '<div class="card"><div class="k">BRIDGE UPTIME</div><div class="v" style="font-size:20px">__U__</div></div>'
        '<div class="card wide"><div class="k">TOP LOCATION</div>'
        '<div class="v" style="font-size:20px">__T____TE__</div></div>'
        '</div>'
        '<a class="back" href="/">&larr; Back to phone</a>'
        '<a class="back" href="/news">Herald</a>'
        '<a class="back" href="/spectate">Spectate</a>'
        '<div class="foot">Camera stays gallery-only · NEWS is separate · Win7 stdlib bridge · crash-safer CLEO</div>'
        '</div></body></html>'
    )
    return (
        body.replace("__VER__", ver)
        .replace("__P__", str(int(data.get("photo_count_today") or 0)))
        .replace("__N__", str(int(data.get("news_count_today") or 0)))
        .replace("__C__", str(int(data.get("chat_count_today") or 0)))
        .replace("__S__", str(streak))
        .replace("__U__", up)
        .replace("__T__", top_s)
        .replace("__TE__", top_extra)
    )


def render_spectate_html():
    """Snapshot-based live view - refreshes latest bridge photo (not H.264/WebRTC)."""
    ver = STATE.get("version", "unknown") or "unknown"
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width, initial-scale=1, viewport-fit=cover\">"
        "<meta name=\"theme-color\" content=\"#041006\">"
        "<title>GroveLink LIVE SPECTATE</title>"
        "<style>"
        "*{box-sizing:border-box;margin:0;padding:0}"
        "html,body{height:100%;background:#000;color:#d7ffd0;font-family:system-ui,sans-serif;overflow:hidden}"
        "#frame{position:fixed;inset:0;width:100%;height:100%;object-fit:contain;background:#000;display:none}"
        "#wait{position:fixed;inset:0;display:flex;align-items:center;justify-content:center;"
        "flex-direction:column;gap:16px;padding:24px;text-align:center;background:#041006}"
        "#wait h1{font-size:18px;letter-spacing:2px;color:#2cff6a}"
        "#wait p{font-size:14px;color:#7aaa7a;line-height:1.5;max-width:420px}"
        ".badge{position:fixed;top:14px;left:14px;z-index:5;background:#e22;color:#fff;"
        "font-weight:bold;font-size:13px;letter-spacing:2px;padding:8px 14px;border-radius:2px;"
        "box-shadow:0 0 12px rgba(255,40,40,0.55);animation:pulse 1.2s ease-in-out infinite}"
        "@keyframes pulse{0%,100%{opacity:1}50%{opacity:0.65}}"
        ".banner{position:fixed;top:52px;left:14px;right:14px;z-index:5;background:rgba(4,16,6,0.88);"
        "border:1px solid #2cff6a;color:#b6e6b0;font-size:12px;padding:8px 12px;text-align:center;"
        "letter-spacing:0.5px}"
        ".banner b{color:#2cff6a}"
        ".controls{position:fixed;top:14px;right:14px;z-index:6;display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}"
        ".controls a,.controls button{background:#0b0f0c;color:#2cff6a;border:1px solid #2cff6a;"
        "padding:8px 12px;text-decoration:none;font-size:12px;font-weight:bold;cursor:pointer;min-height:40px}"
        ".meta{position:fixed;bottom:12px;left:12px;right:12px;z-index:5;font-size:11px;color:#7aaa7a;"
        "text-align:center;text-shadow:0 1px 3px #000}"
        "body.cinema .badge,body.cinema .banner,body.cinema .controls,body.cinema .meta{display:none!important}"
        "body.cinema #frame{inset:0;width:100vw;height:100vh;object-fit:contain}"
        "body.cinema #wait{inset:0}"
        ".cinema-hint{display:none;position:fixed;bottom:10px;left:50%;transform:translateX(-50%);z-index:8;"
        "font-size:11px;color:#7aaa7a;background:rgba(0,0,0,0.5);padding:4px 10px;border-radius:2px}"
        "body.cinema .cinema-hint{display:block}"
        "</style></head><body>"
        "<div class=\"badge\" id=\"badge\">LIVE SPECTATE</div>"
        "<div class=\"banner\" id=\"banner\"><b>Snapshot live - not video</b> · slideshow of camera stills · same Wi-Fi + bridge · <span id=\"watching\">0 watching</span></div>"
        "<div class=\"controls\">"
        "<button type=\"button\" id=\"btn_pause\">Pause</button>"
        "<button type=\"button\" id=\"btn_fs\">Fullscreen</button>"
        "<button type=\"button\" id=\"btn_cinema\" title=\"Hide chrome (H)\">Cinema</button>"
        "<button type=\"button\" id=\"btn_dl\" title=\"Download current frame\">Download</button>"
        "<a class=\"back\" href=\"/\">← Phone</a>"
        "</div>"
        "<div class=\"cinema-hint\" id=\"cinema_hint\">Press H to show controls</div>"
        "<img id=\"frame\" alt=\"spectate frame\">"
        "<div id=\"wait\">"
        "<h1>WAITING FOR SPECTATE FRAMES</h1>"
        "<p>Enable <b>SPECTATE</b> in-game (K → SPECTATE → Enter). "
        "Snapshot slideshow only - not real video. Same Wi-Fi + bridge must run.</p>"
        "</div>"
        "<div class=\"meta\" id=\"meta\">GroveLink __VER__ · snapshot live - not video</div>"
        "<script>"
        "var img=document.getElementById('frame');"
        "var wait=document.getElementById('wait');"
        "var meta=document.getElementById('meta');"
        "var last='';"
        "var paused=false;"
        "var timer=null;"
        "var pollMs=750;"
        "function ageLabel(sec){"
        "  sec=parseInt(sec,10)||0;"
        "  if(sec<5) return 'just now';"
        "  if(sec<60) return sec+'s ago';"
        "  return Math.floor(sec/60)+'m '+ (sec%60) +'s ago';"
        "}"
        "function tick(){"
        "  if(paused) return;"
        "  var x=new XMLHttpRequest();"
        "  x.open('GET','/api/spectate',true);"
        "  x.timeout=4000;"
        "  x.onload=function(){"
        "    try{"
        "      var j=JSON.parse(x.responseText||'{}');"
        "      var url=j.latest_url||'';"
        "      var on=!!j.spectate_on;"
        "      var name=j.latest||'';"
        "      if(j.poll_ms){ var pm=parseInt(j.poll_ms,10); if(pm>=200&&pm<=5000) pollMs=pm; }"
        "      if(url){"
        "        var bust=url+(url.indexOf('?')>=0?'&':'?')+'t='+(j.last_refresh||Date.now());"
        "        if(bust!==last){ last=bust; img.src=bust; }"
        "        img.style.display='block'; wait.style.display='none';"
        "      } else {"
        "        img.style.display='none'; wait.style.display='flex';"
        "      }"
        "      var w=parseInt(j.watching||0,10)||0;"
        "      var wel=document.getElementById('watching');"
        "      if(wel) wel.textContent=w+' watching';"
        "      meta.textContent='GroveLink '+ (j.version||'') +"
        "        (on?' · SPECTATE ON':' · SPECTATE off in-game') +"
        "        (name?' · '+name:'') +"
        "        ' · frame '+ ageLabel(j.age_sec) +"
        "        ' · '+w+' watching' +"
        "        ' · snapshot live - not video';"
        "      schedule();"
        "    }catch(e){ schedule(); }"
        "  };"
        "  x.onerror=function(){ meta.textContent='Bridge offline - run START_GROVELINK'; schedule(); };"
        "  x.ontimeout=function(){ schedule(); };"
        "  x.send();"
        "}"
        "function schedule(){"
        "  if(timer) clearTimeout(timer);"
        "  if(paused) return;"
        "  timer=setTimeout(tick, pollMs);"
        "}"
        "document.getElementById('btn_pause').onclick=function(){"
        "  paused=!paused;"
        "  this.textContent=paused?'Resume':'Pause';"
        "  if(!paused) tick(); else if(timer) clearTimeout(timer);"
        "};"
        "document.getElementById('btn_fs').onclick=function(){"
        "  var el=document.documentElement;"
        "  try{"
        "    if(!document.fullscreenElement && !document.webkitFullscreenElement){"
        "      if(el.requestFullscreen) el.requestFullscreen();"
        "      else if(el.webkitRequestFullscreen) el.webkitRequestFullscreen();"
        "    } else {"
        "      if(document.exitFullscreen) document.exitFullscreen();"
        "      else if(document.webkitExitFullscreen) document.webkitExitFullscreen();"
        "    }"
        "  }catch(e){}"
        "};"
        "document.getElementById('btn_dl').onclick=function(){"
"  var s=img&&img.src?img.src:'';"
"  if(!s){ return; }"
"  try{"
"    var a=document.createElement('a');"
"    a.href=s; a.download='grovelink-spectate.jpg'; a.target='_blank'; a.rel='noopener';"
"    document.body.appendChild(a); a.click(); document.body.removeChild(a);"
"  }catch(e){ try{ window.open(s,'_blank'); }catch(e2){} }"
"};"
"function setCinema(on){"
"  document.body.className=on?'cinema':'';"
        "  var b=document.getElementById('btn_cinema');"
        "  if(b) b.textContent=on?'Exit cinema':'Cinema';"
        "  try{ localStorage.setItem('grovelink_cinema', on?'1':'0'); }catch(e){}"
        "}"
        "document.getElementById('btn_cinema').onclick=function(){"
        "  setCinema(document.body.className.indexOf('cinema')<0);"
        "};"
        "document.addEventListener('keydown',function(ev){"
        "  var t=(ev.target&&ev.target.tagName)||'';"
        "  if(t==='INPUT'||t==='TEXTAREA') return;"
        "  if(ev.key==='h'||ev.key==='H'){"
        "    setCinema(document.body.className.indexOf('cinema')<0);"
        "  }"
        "});"
        "try{ if(localStorage.getItem('grovelink_cinema')==='1') setCinema(true); }catch(e){}"
        "tick();"
        "</script></body></html>"
    ).replace('__VER__', _esc(ver))



def render_live_html():
    """Watch party: spectate iframe on top, sticky chat below (mobile-friendly)."""
    ver = STATE.get("version", "unknown") or "unknown"
    ip = STATE.get("ip", "127.0.0.1")
    port = STATE.get("port", 8088)
    return (
        "<!DOCTYPE html><html><head><meta charset=\"utf-8\">"
        "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,maximum-scale=1\">"
        "<meta name=\"theme-color\" content=\"#0a1f0a\">"
        "<title>GroveLink Watch Party</title>"
        "<style>"
        "html,body{margin:0;padding:0;background:#061206;color:#c8f0c8;font-family:Segoe UI,Arial,sans-serif;height:100%;}"
        ".wrap{display:flex;flex-direction:column;height:100vh;max-height:100%;}"
        ".top{flex:1 1 55%;min-height:180px;background:#000;position:relative;border-bottom:2px solid #2ecc71;}"
        ".top iframe{width:100%;height:100%;border:0;display:block;}"
        ".badge{position:absolute;top:8px;left:8px;background:rgba(10,40,10,0.85);border:1px solid #2ecc71;"
        "color:#7CFF7C;padding:4px 10px;border-radius:999px;font-size:12px;z-index:2;}"
        ".bot{flex:1 1 45%;min-height:200px;display:flex;flex-direction:column;overflow:hidden;}"
        ".bar{padding:8px 12px;background:#0d220d;border-bottom:1px solid #1a4a1a;font-size:13px;display:flex;gap:10px;flex-wrap:wrap;align-items:center;}"
        ".bar a{color:#7CFF7C;}"
        ".chat{flex:1;overflow:auto;padding:10px 12px;}"
        ".row{margin:0 0 8px;padding:8px 10px;border-radius:10px;background:#102810;border:1px solid #1e4a1e;max-width:92%;}"
        ".row.cj{background:#143214;border-color:#2ecc71;margin-left:auto;}"
        ".row.sys{background:#1a2a12;border-color:#c4a35a;font-style:italic;}"
        ".meta{font-size:10px;color:#7aaa7a;margin-bottom:3px;}"
        ".composer{display:flex;gap:8px;padding:10px;background:#0d220d;border-top:1px solid #1a4a1a;}"
        ".composer input{flex:1;padding:10px;border-radius:8px;border:1px solid #2ecc71;background:#061206;color:#c8f0c8;}"
        ".composer button{padding:10px 14px;border-radius:8px;border:0;background:#2ecc71;color:#041204;font-weight:700;}"
        ".empty{color:#6a9a6a;font-size:13px;padding:12px;}"
        "@media(min-width:900px){.wrap{flex-direction:row;}.top{flex:1 1 60%;border-bottom:0;border-right:2px solid #2ecc71;}.bot{flex:1 1 40%;}}"
        "</style></head><body>"
        "<div class=\"wrap\">"
        "<div class=\"top\"><div class=\"badge\">WATCH PARTY · v" + _esc(ver) + "</div>"
        "<iframe src=\"/spectate\" title=\"LIVE SPECTATE\"></iframe></div>"
        "<div class=\"bot\">"
        "<div class=\"bar\"><b>Chat with CJ</b> · <a href=\"/\">Phone page</a> · <a href=\"/spectate\">Spectate only</a>"
        " · <span id=\"vc\">0 viewers</span></div>"
        "<div class=\"chat\" id=\"chat\"><div class=\"empty\">Waiting for messages… text CJ below.</div></div>"
        "<div class=\"composer\"><input id=\"msg\" maxlength=\"80\" placeholder=\"Message to CJ…\">"
        "<button type=\"button\" id=\"send\">SEND</button></div>"
        "</div></div>"
        "<script>"
        "(function(){"
        "function esc(s){return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/\"/g,'&quot;').replace(/'/g,'&#39;');}"
        "function nick(){try{return localStorage.getItem('grovelink_nickname')||'REAL PHONE';}catch(e){return 'REAL PHONE';}}"
        "function paint(inbox, viewers){"
        "  var el=document.getElementById('chat'); if(!el) return;"
        "  var rows=(inbox||[]).slice().reverse();"
        "  if(!rows.length){el.innerHTML='<div class=\"empty\">Waiting for viewers / messages…</div>';}"
        "  else{var h=''; for(var i=0;i<rows.length;i++){var m=rows[i]||{};"
        "    var cls='row'; if(m.role==='cj'||m.side==='cj') cls+=' cj'; if(m.broadcast||m.system) cls+=' sys';"
        "    h+='<div class=\"'+cls+'\"><div class=\"meta\">'+esc(m.from||'?')+' · '+esc(m.when||'')+"
        "      (m.broadcast?' · BROADCAST':'')+'</div>'+esc(m.msg||'')+'</div>';}"
        "    el.innerHTML=h; el.scrollTop=el.scrollHeight;}"
        "  var vc=document.getElementById('vc');"
        "  if(vc){var n=(viewers&&viewers.length)||0; vc.textContent=n+' viewer'+(n===1?'':'s');}"
        "}"
        "function poll(){var x=new XMLHttpRequest(); x.open('GET','/api',true); x.onreadystatechange=function(){"
        "  if(x.readyState===4&&x.status===200){try{var j=JSON.parse(x.responseText); paint(j.inbox,j.viewers);}catch(e){}}"
        "}; x.send();}"
        "function send(){var inp=document.getElementById('msg'); var msg=(inp&&inp.value||'').trim(); if(!msg)return;"
        "  var body='msg='+encodeURIComponent(msg)+'&from='+encodeURIComponent(nick());"
        "  var x=new XMLHttpRequest(); x.open('POST','/send',true);"
        "  x.setRequestHeader('Content-Type','application/x-www-form-urlencoded');"
        "  x.onreadystatechange=function(){if(x.readyState===4){if(x.status===200){if(inp)inp.value=''; poll();}"
        "    else if(x.status===429){alert('Slow down — 1 text / 3s');}else{alert('Send failed');}}};"
        "  x.send(body);}"
        "document.getElementById('send').onclick=send;"
        "document.getElementById('msg').onkeydown=function(e){if(e.keyCode===13){e.preventDefault();send();}};"
        "poll(); setInterval(poll,2000);"
        "})();</script></body></html>"
    )


def spectate_payload():
    photos = STATE.get("photos", [])
    latest = ""
    if photos:
        latest = photos[0].get("file") or ""
    spectate_on = bool(STATE.get("spectate_on"))
    try:
        ini = STATE.get("link_ini") or ""
        if ini:
            spectate_on = read_ini_key(ini, "SPECTATE", "on", "0") == "1"
            STATE["spectate_on"] = spectate_on
    except Exception:
        pass
    last_ref = int(STATE.get("last_refresh", 0) or 0)
    age_sec = 0
    if last_ref:
        try:
            age_sec = max(0, int(time.time()) - last_ref)
        except Exception:
            age_sec = 0
    # Hotter poll hint when SPECTATE.on (client uses this)
    poll_ms = 400 if spectate_on else 750
    return {
        "ok": True,
        "spectate_on": spectate_on,
        "latest": latest,
        "latest_url": ("/photo/%s" % latest) if latest else "",
        "last_refresh": last_ref,
        "age_sec": age_sec,
        "poll_ms": poll_ms,
        "watching": spectate_watching_count(),
        "version": STATE.get("version", "unknown") or "unknown",
        "note": "snapshot live - not video",
    }



def api_payload():
    ip = STATE.get("ip", "127.0.0.1")
    port = STATE.get("port", 8088)
    photos = STATE.get("photos", [])
    try:
        photos = attach_captions_to_photos(photos)
    except Exception:
        pass
    try:
        photos = attach_favorites_to_photos(photos)
    except Exception:
        pass
    try:
        photos = attach_locations_to_photos(photos)
    except Exception:
        pass
    try:
        photos = attach_comments_to_photos(photos)
    except Exception:
        pass
    try:
        note_streak_from_photos(photos)
    except Exception:
        pass
    latest = ""
    if photos:
        latest = photos[0].get("file") or ""
    inbox = STATE.get("inbox", [])
    try:
        chat = load_chat_log()
        if chat:
            inbox = chat
    except Exception:
        pass
    latest_url = ("/photo/%s" % latest) if latest else ""
    try:
        _streak = streak_payload()
    except Exception:
        _streak = {"streak": 0, "photo_days": 0, "dates": []}
    spectate_on = bool(STATE.get("spectate_on"))
    try:
        ini = STATE.get("link_ini") or ""
        if ini:
            spectate_on = read_ini_key(ini, "SPECTATE", "on", "0") == "1"
            STATE["spectate_on"] = spectate_on
    except Exception:
        pass
    return {
        "ok": True,
        "bridge_ok": bool(STATE.get("bridge_ok", True)),
        "photos": photos,
        "inbox": inbox,
        "photo_count": len(photos),
        "count": len(photos),
        "latest": latest,
        "latest_url": latest_url,
        "spectate_on": spectate_on,
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
        "news_count": len(list_news_articles(5)),
        "favorites": sorted(load_favorites()),
        "hud": read_hud_from_ini(),
        "watching": spectate_watching_count(),
        "places": places_summary(photos),
        "uptime_sec": bridge_uptime_sec(),
        "uptime_human": format_uptime(bridge_uptime_sec()),
        "pinned": get_pinned_chat(),
        "pinned_chat_id": (STATE.get("pinned_chat_id") or ""),
        "streak": _streak.get("streak", 0),
        "photo_days": _streak.get("photo_days", 0),
        "streak_dates": _streak.get("dates") or [],
        "viewers": list_active_viewers(),
        "viewer_count": len(list_active_viewers()),
        "poll": poll_payload(),
        "requests": pending_requests(),
        "request_kinds": list(ALLOWED_REQUEST_KINDS),
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
        "latest_url": ("/photo/%s" % latest) if latest else "",
        "spectate_on": bool(STATE.get("spectate_on")),
        "galleries": list(STATE.get("galleries", [])),
        "ip": STATE.get("ip", "127.0.0.1"),
        "port": STATE.get("port", 8088),
        "gta_dir": STATE.get("gta_dir", "") or "",
        "version": STATE.get("version", "unknown") or "unknown",
        "poll_ms": int(STATE.get("poll_ms") or 2000),
        "max_photos": int(STATE.get("max_photos") or 40),
        "last_error": STATE.get("last_error", "") or "",
        "skipped_deleted": len(DELETED),
        "uptime_sec": bridge_uptime_sec(),
        "uptime_human": format_uptime(bridge_uptime_sec()),
        "started_at": int(STATE.get("started_at") or 0),
        "streak": streak_payload().get("streak", 0),
        "photo_days": streak_payload().get("photo_days", 0),
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
        if path == "/news" or path == "/news/":
            self._html(render_news_index())
            return
        if path.startswith("/news/"):
            art_id = unquote(path[len("/news/"):]).strip("/")
            art_id = os.path.basename(art_id)
            page = render_news_article_page(art_id)
            if not page:
                self.send_error(404)
                return
            self._html(page)
            return
        if path == "/api/chat":
            self._json({
                "ok": True,
                "inbox": load_chat_log(),
                "pinned": get_pinned_chat(),
                "pinned_chat_id": (STATE.get("pinned_chat_id") or ""),
            })
            return
        if path == "/recap" or path == "/recap/":
            self._html(render_recap_html())
            return
        if path == "/api/spectate":
            try:
                cip = self.client_address[0] if self.client_address else ""
                note_spectate_viewer(cip)
            except Exception:
                pass
            self._json(spectate_payload())
            return
        if path == "/spectate" or path == "/spectate/":
            try:
                cip = self.client_address[0] if self.client_address else ""
                note_spectate_viewer(cip)
            except Exception:
                pass
            self._html(render_spectate_html())
            return
        if path == "/manifest.webmanifest" or path == "/manifest.json":
            body = json.dumps(render_manifest())
            data = body.encode("utf-8") if not isinstance(body, bytes) else body
            self.send_response(200)
            self.send_header("Content-Type", "application/manifest+json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/favorite" or path == "/favorites":
            # GET list of favorites
            self._json({"ok": True, "favorites": sorted(load_favorites())})
            return
        if path == "/live" or path == "/live/":
            self._html(render_live_html())
            return
        if path == "/api/poll":
            self._json({"ok": True, "poll": poll_payload()})
            return
        if path == "/api/requests":
            self._json({"ok": True, "requests": load_requests(), "pending": pending_requests()})
            return
        if path == "/api/viewers":
            self._json({"ok": True, "viewers": list_active_viewers()})
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
            # Require confirm=1 (same as GET /clear) - accidental wipe guard
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

        if path == "/favorite" or path == "/favorites":
            name = ""
            fav_flag = "1"
            if text_body.lstrip().startswith("{"):
                try:
                    obj = json.loads(text_body)
                    name = obj.get("file") or obj.get("name") or ""
                    if "favorite" in obj:
                        fav_flag = str(obj.get("favorite"))
                    elif "on" in obj:
                        fav_flag = str(obj.get("on"))
                except Exception:
                    name = ""
            else:
                fields = parse_qs(text_body)
                if "file" in fields and fields["file"]:
                    name = fields["file"][0]
                if "favorite" in fields and fields["favorite"]:
                    fav_flag = fields["favorite"][0]
                elif "on" in fields and fields["on"]:
                    fav_flag = fields["on"][0]
            if not name and "?" in self.path:
                qfields = parse_qs(self.path.split("?", 1)[1])
                if "file" in qfields and qfields["file"]:
                    name = qfields["file"][0]
                if "favorite" in qfields and qfields["favorite"]:
                    fav_flag = qfields["favorite"][0]
            on = str(fav_flag).strip().lower() in ("1", "true", "yes", "on")
            ok, detail = set_favorite(name, on)
            code = 200 if ok else 400
            self._json({
                "ok": ok,
                "file": _safe_basename(name),
                "favorite": on if ok else False,
                "favorites": sorted(load_favorites()),
                "detail": detail,
            }, code=code)
            return

        if path == "/caption":
            name = ""
            caption = ""
            if text_body.lstrip().startswith("{"):
                try:
                    obj = json.loads(text_body)
                    name = obj.get("file") or obj.get("name") or ""
                    caption = obj.get("caption") or ""
                except Exception:
                    name = ""
            else:
                fields = parse_qs(text_body)
                if "file" in fields and fields["file"]:
                    name = fields["file"][0]
                if "caption" in fields and fields["caption"]:
                    caption = fields["caption"][0]
            ok, detail = set_caption(name, caption)
            # Refresh captions on STATE photos
            try:
                STATE["photos"] = attach_captions_to_photos(STATE.get("photos", []))
            except Exception:
                pass
            code = 200 if ok else 400
            self._json({"ok": ok, "file": _safe_basename(name), "caption": detail}, code=code)
            return

        if path == "/comment":
            name = ""
            comment = ""
            if text_body.lstrip().startswith("{"):
                try:
                    obj = json.loads(text_body)
                    name = obj.get("file") or obj.get("name") or ""
                    comment = obj.get("comment") or obj.get("text") or ""
                except Exception:
                    name = ""
            else:
                fields = parse_qs(text_body)
                if "file" in fields and fields["file"]:
                    name = fields["file"][0]
                if "comment" in fields and fields["comment"]:
                    comment = fields["comment"][0]
                elif "text" in fields and fields["text"]:
                    comment = fields["text"][0]
            ok, detail = set_comment(name, comment)
            try:
                STATE["photos"] = attach_comments_to_photos(STATE.get("photos", []))
            except Exception:
                pass
            code = 200 if ok else 400
            self._json({"ok": ok, "file": _safe_basename(name), "comment": detail}, code=code)
            return

        if path == "/news":
            name = ""
            caption = ""
            location = ""
            if text_body.lstrip().startswith("{"):
                try:
                    obj = json.loads(text_body)
                    name = obj.get("file") or obj.get("photo") or ""
                    caption = obj.get("caption") or ""
                    location = obj.get("location") or obj.get("zone") or obj.get("loc") or ""
                except Exception:
                    name = ""
            else:
                fields = parse_qs(text_body)
                if "file" in fields and fields["file"]:
                    name = fields["file"][0]
                elif "photo" in fields and fields["photo"]:
                    name = fields["photo"][0]
                if "caption" in fields and fields["caption"]:
                    caption = fields["caption"][0]
                if "location" in fields and fields["location"]:
                    location = fields["location"][0]
                elif "zone" in fields and fields["zone"]:
                    location = fields["zone"][0]
                elif "loc" in fields and fields["loc"]:
                    location = fields["loc"][0]
            link = getattr(self.server, "link_ini", None) or STATE.get("link_ini") or ""
            ok, article, detail = create_news_from_photo(
                name, caption=caption, auto=False, link_ini=link, location=location
            )
            if not ok or not article:
                self._json({"ok": False, "detail": detail or "failed"}, code=400)
                return
            self._json({
                "ok": True,
                "id": article.get("id"),
                "headline": article.get("headline"),
                "location": article.get("location") or "",
                "url": "/news/%s" % article.get("id"),
            })
            return

        if path == "/react" or path == "/api/chat/react":
            msg_id = ""
            emoji = ""
            if text_body.lstrip().startswith("{"):
                try:
                    obj = json.loads(text_body)
                    msg_id = obj.get("id") or obj.get("msg_id") or ""
                    emoji = obj.get("reaction") or obj.get("emoji") or obj.get("r") or ""
                except Exception:
                    msg_id = ""
            else:
                fields = parse_qs(text_body)
                if "id" in fields and fields["id"]:
                    msg_id = fields["id"][0]
                elif "msg_id" in fields and fields["msg_id"]:
                    msg_id = fields["msg_id"][0]
                if "reaction" in fields and fields["reaction"]:
                    emoji = fields["reaction"][0]
                elif "emoji" in fields and fields["emoji"]:
                    emoji = fields["emoji"][0]
                elif "r" in fields and fields["r"]:
                    emoji = fields["r"][0]
            ok, detail = react_to_chat(msg_id, emoji)
            if not ok:
                self._json({"ok": False, "detail": detail}, code=400)
                return
            try:
                # Best-effort: nick from body if present
                nick = ""
                if text_body.lstrip().startswith("{"):
                    try:
                        nick = (json.loads(text_body).get("from") or json.loads(text_body).get("name") or "")
                    except Exception:
                        nick = ""
                else:
                    rf = parse_qs(text_body)
                    if "from" in rf and rf["from"]:
                        nick = rf["from"][0]
                    elif "name" in rf and rf["name"]:
                        nick = rf["name"][0]
                if nick:
                    note_active_viewer(nick, _client_ip_from_handler(self))
                else:
                    note_active_viewer("Viewer", _client_ip_from_handler(self))
            except Exception:
                pass
            self._json({
                "ok": True,
                "entry": detail,
                "id": detail.get("id") if isinstance(detail, dict) else msg_id,
                "reactions": (detail.get("reactions") if isinstance(detail, dict) else {}),
                "pinned": get_pinned_chat(),
            })
            return

        if path == "/pin" or path == "/api/chat/pin":
            msg_id = ""
            if text_body.lstrip().startswith("{"):
                try:
                    obj = json.loads(text_body)
                    msg_id = obj.get("id") or obj.get("msg_id") or ""
                    if obj.get("clear") in (1, True, "1", "true", "yes"):
                        msg_id = ""
                except Exception:
                    msg_id = ""
            else:
                fields = parse_qs(text_body)
                if "id" in fields and fields["id"]:
                    msg_id = fields["id"][0]
                elif "msg_id" in fields and fields["msg_id"]:
                    msg_id = fields["msg_id"][0]
                if "clear" in fields and fields["clear"] and fields["clear"][0] in ("1", "true", "yes"):
                    msg_id = ""
            ok, entry, detail = pin_chat_message(msg_id)
            code = 200 if ok else 404
            self._json({
                "ok": ok,
                "detail": detail,
                "pinned": entry,
                "pinned_chat_id": (STATE.get("pinned_chat_id") or ""),
            }, code=code)
            return

        # --- 2.4.0 interactive POSTs ---
        if path == "/broadcast" or path == "/api/broadcast":
            msg = ""
            frm = "CJ"
            if text_body.lstrip().startswith("{"):
                try:
                    obj = json.loads(text_body)
                    msg = obj.get("msg") or obj.get("message") or ""
                    frm = obj.get("from") or frm
                except Exception:
                    msg = ""
            else:
                fields = parse_qs(text_body)
                if "msg" in fields and fields["msg"]:
                    msg = fields["msg"][0]
                elif "message" in fields and fields["message"]:
                    msg = fields["message"][0]
                if "from" in fields and fields["from"]:
                    frm = fields["from"][0]
            ok, entry, detail = do_broadcast(msg, frm)
            if not ok:
                self._json({"ok": False, "detail": detail}, code=400)
                return
            self._json({"ok": True, "entry": entry, "detail": detail, "broadcast": True})
            return

        if path == "/request" or path == "/api/request":
            kind = ""
            frm = "Viewer"
            action = ""
            req_id = ""
            if text_body.lstrip().startswith("{"):
                try:
                    obj = json.loads(text_body)
                    kind = obj.get("kind") or obj.get("request") or ""
                    frm = obj.get("from") or obj.get("name") or frm
                    action = str(obj.get("action") or obj.get("status") or "")
                    req_id = obj.get("id") or ""
                    if obj.get("done") in (1, True, "1", "true", "yes"):
                        action = "done"
                    if obj.get("clear") in (1, True, "1", "true", "yes"):
                        action = "clear"
                except Exception:
                    kind = ""
            else:
                fields = parse_qs(text_body)
                if "kind" in fields and fields["kind"]:
                    kind = fields["kind"][0]
                elif "request" in fields and fields["request"]:
                    kind = fields["request"][0]
                if "from" in fields and fields["from"]:
                    frm = fields["from"][0]
                elif "name" in fields and fields["name"]:
                    frm = fields["name"][0]
                if "action" in fields and fields["action"]:
                    action = fields["action"][0]
                if "id" in fields and fields["id"]:
                    req_id = fields["id"][0]
                if "done" in fields and fields["done"] and fields["done"][0] in ("1", "true", "yes"):
                    action = "done"
                if "clear" in fields and fields["clear"] and fields["clear"][0] in ("1", "true", "yes"):
                    action = "clear"
            cip = _client_ip_from_handler(self)
            action = (action or "").strip().lower()
            if action in ("done", "complete", "mark_done"):
                ok, detail = mark_request_done(req_id, clear_all=False)
                code = 200 if ok else 404
                self._json({"ok": ok, "detail": detail, "pending": pending_requests()}, code=code)
                return
            if action in ("clear", "clear_all"):
                ok, detail = mark_request_done("", clear_all=True)
                self._json({"ok": ok, "detail": detail, "pending": pending_requests()})
                return
            ok, entry, detail = enqueue_request(kind, frm, ip=cip)
            if not ok:
                self._json({"ok": False, "detail": detail}, code=400)
                return
            self._json({"ok": True, "request": entry, "detail": detail, "pending": pending_requests()})
            return

        if path == "/poll" or path == "/api/poll":
            question = ""
            options = []
            action = ""
            if text_body.lstrip().startswith("{"):
                try:
                    obj = json.loads(text_body)
                    question = obj.get("question") or obj.get("q") or ""
                    options = obj.get("options") or obj.get("opts") or []
                    action = str(obj.get("action") or "")
                    if obj.get("close") in (1, True, "1", "true", "yes"):
                        action = "close"
                except Exception:
                    question = ""
            else:
                fields = parse_qs(text_body)
                if "question" in fields and fields["question"]:
                    question = fields["question"][0]
                elif "q" in fields and fields["q"]:
                    question = fields["q"][0]
                if "options" in fields and fields["options"]:
                    options = fields["options"][0]
                elif "opts" in fields and fields["opts"]:
                    options = fields["opts"][0]
                if "option" in fields:
                    options = fields.get("option") or options
                if "action" in fields and fields["action"]:
                    action = fields["action"][0]
                if "close" in fields and fields["close"] and fields["close"][0] in ("1", "true", "yes"):
                    action = "close"
            action = (action or "").strip().lower()
            if action in ("close", "end"):
                ok, poll, detail = close_poll(write_inbox=True)
                code = 200 if ok else 400
                self._json({"ok": ok, "poll": poll_payload(poll), "detail": detail}, code=code)
                return
            ok, poll, detail = create_poll(question, options, frm="Host")
            if not ok:
                self._json({"ok": False, "detail": detail}, code=400)
                return
            self._json({"ok": True, "poll": poll_payload(poll), "detail": detail})
            return

        if path == "/vote" or path == "/api/vote":
            option = ""
            nick = ""
            if text_body.lstrip().startswith("{"):
                try:
                    obj = json.loads(text_body)
                    option = obj.get("option")
                    if option is None:
                        option = obj.get("index")
                    if option is None:
                        option = obj.get("vote")
                    nick = obj.get("from") or obj.get("name") or ""
                except Exception:
                    option = ""
            else:
                fields = parse_qs(text_body)
                if "option" in fields and fields["option"]:
                    option = fields["option"][0]
                elif "index" in fields and fields["index"]:
                    option = fields["index"][0]
                elif "vote" in fields and fields["vote"]:
                    option = fields["vote"][0]
                if "from" in fields and fields["from"]:
                    nick = fields["from"][0]
                elif "name" in fields and fields["name"]:
                    nick = fields["name"][0]
            cip = _client_ip_from_handler(self)
            ok, poll, detail = vote_poll(option, ip=cip, nick=nick)
            code = 200 if ok else 400
            self._json({"ok": ok, "poll": poll_payload(poll), "detail": detail}, code=code)
            return

        if path != "/send":
            self.send_error(404)
            return
        msg = ""
        frm = "REAL PHONE"
        if text_body.lstrip().startswith("{"):
            try:
                obj = json.loads(text_body)
                msg = obj.get("msg") or ""
                frm = obj.get("from") or obj.get("name") or frm
            except Exception:
                msg = ""
        else:
            fields = parse_qs(text_body)
            if "msg" in fields and fields["msg"]:
                msg = fields["msg"][0]
            if "from" in fields and fields["from"]:
                frm = fields["from"][0]
            elif "name" in fields and fields["name"]:
                frm = fields["name"][0]
        msg = (msg or "").strip().replace("\r", " ").replace("\n", " ")[:80]
        frm = (frm or "REAL PHONE").strip().replace("\r", " ").replace("\n", " ")[:40] or "REAL PHONE"
        if msg:
            cip = _client_ip_from_handler(self)
            ok_rl, wait = check_send_rate_limit(cip)
            if not ok_rl:
                self._json({
                    "ok": False,
                    "delivered": False,
                    "detail": "rate limit: wait %.1fs between texts" % wait,
                    "retry_after": wait,
                }, code=429)
                return
            entry = append_chat_delivered(frm, msg)
            note_active_viewer(frm, cip)
            STATE["sent"] = STATE.get("sent", 0) + 1
            write_ini_kv(self.server.link_ini, "INBOX", {
                "new": "1",
                "from": frm.replace("=", "-"),
                "msg": msg.replace("=", "-"),
            })
            print("SMS -> GTA:", frm, msg)
            self._json({"ok": True, "delivered": True, "from": frm, "msg": msg, "entry": entry})
            return
        self._json({"ok": True, "delivered": False})



def shutter_burst(cfg, gta_dir, seconds=3.0, interval=0.25):
    """After PHOTO.take / NEWS.make flips, poll/copy aggressively for a few seconds.
    Never creates news - Camera gallery path stays news-free."""
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


def process_photo_and_news_flags(cfg, gta_dir, ini, burst_seconds=3.5, burst_interval=0.25):
    """Handle CLEO flags in link.ini.

    PHOTO.take alone (Camera): burst-copy gallery → phone page. Never creates news.
    NEWS.make (NEWS menu): burst-copy like shutter, then create_news_from_photo on
    newest bridge photo (with NEWS.zone/loc) and set NEWS.new=1 for CLEO toast.
    SPECTATE.frame: burst-copy for /spectate live view. Never creates news.
    """
    take = read_ini_key(ini, "PHOTO", "take", "0")
    make = read_ini_key(ini, "NEWS", "make", "0")
    frame = read_ini_key(ini, "SPECTATE", "frame", "0")
    try:
        STATE["spectate_on"] = read_ini_key(ini, "SPECTATE", "on", "0") == "1"
    except Exception:
        pass
    if take != "1" and make != "1" and frame != "1":
        return False
    news_location = ""
    if make == "1":
        news_location = (
            read_ini_key(ini, "NEWS", "zone", "")
            or read_ini_key(ini, "NEWS", "loc", "")
        )
    if take == "1":
        write_ini_kv(ini, "PHOTO", {"take": "0"})
    if make == "1":
        write_ini_kv(ini, "NEWS", {"make": "0", "zone": ""})
    if frame == "1":
        write_ini_kv(ini, "SPECTATE", {"frame": "0"})
    if make == "1":
        label = "News snap"
    elif frame == "1" and take != "1":
        label = "Spectate frame"
        # Spectate frames: shorter burst - keep live view snappy, still no NEWS
        burst_seconds = min(burst_seconds, 2.0)
    else:
        label = "Shutter"
    print("%s - fast poll for new Gallery files..." % label)
    shutter_burst(cfg, gta_dir, seconds=burst_seconds, interval=burst_interval)
    if make == "1":
        newest = None
        photos = STATE.get("photos") or []
        if photos and isinstance(photos[0], dict):
            newest = photos[0].get("file")
        if newest:
            try:
                ok, art, detail = create_news_from_photo(
                    newest,
                    caption=get_caption(newest),
                    auto=False,
                    link_ini=ini,
                    location=news_location,
                )
                if ok and art:
                    print(
                        "Breaking News filed:",
                        art.get("id"),
                        (art.get("headline") or "")[:60],
                        ("@ " + (art.get("location") or "")) if art.get("location") else "",
                    )
                else:
                    print("Breaking News failed:", detail)
            except Exception as exc:
                print("news make error:", exc)
        else:
            print("Breaking News: no bridge photo yet after burst")
    # SPECTATE.frame / PHOTO.take never create news
    print("%s done. Phone page has" % label, len(STATE["photos"]), "shots")
    return True


def watcher(cfg, gta_dir, ini):
    """Poll Gallery folders forever. Re-detect dirs each loop so a folder
    created after the first in-game photo is picked up (startup may have
    found none). PHOTO.take / NEWS.make trigger burst; only NEWS.make files Herald."""
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
                    print("Galleries  : still none - waiting for folder/photos")
                last_galleries = list(galleries)
            copy_latest(galleries)
            try:
                process_outbox_flag(ini)
            except Exception as exc:
                print("outbox watch error:", exc)
            try:
                process_poll_section(ini)
            except Exception as exc:
                print("poll watch error:", exc)
            if process_photo_and_news_flags(cfg, gta_dir, ini):
                # Race fix: another snap/make/frame may have arrived during burst - loop now
                if (
                    read_ini_key(ini, "PHOTO", "take", "0") == "1"
                    or read_ini_key(ini, "NEWS", "make", "0") == "1"
                    or read_ini_key(ini, "SPECTATE", "frame", "0") == "1"
                ):
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
    STATE["link_ini"] = ini
    STATE["started_at"] = int(time.time())
    if not STATE.get("pinned_chat_id"):
        STATE["pinned_chat_id"] = ""
    try:
        STATE["spectate_on"] = read_ini_key(ini, "SPECTATE", "on", "0") == "1"
    except Exception:
        STATE["spectate_on"] = False
    try:
        STATE["inbox"] = load_chat_log()
    except Exception:
        STATE["inbox"] = []

    print("================================================")
    print("  GROVELINK PHONE BRIDGE")
    print("  Version    :", STATE["version"])
    print("================================================")
    print("GTA folder :", gta_dir or "(not found - edit config.ini)")
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
    print("  Grove Street Herald (fake news):")
    print("      http://127.0.0.1:%s/news" % port)
    print("  LIVE SPECTATE (snapshot slideshow):")
    print("      http://127.0.0.1:%s/spectate" % port)
    print("  Camera = gallery only; NEWS menu / web Breaking News = Herald")
    print("  CJ REPLY (OUTBOX) + SPECTATE.frame - never auto-news")
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

    try:
        server = HTTPServer(("0.0.0.0", port), Handler)
    except (OSError, socket.error) as exc:
        # Plain English for Win7 beginners (EADDRINUSE / WSAEADDRINUSE)
        err = str(exc).lower()
        busy = (
            "address already in use" in err
            or "only one usage of each socket address" in err
            or getattr(exc, "errno", None) in (98, 10048)  # Linux EADDRINUSE / Win WSAEADDRINUSE
            or getattr(exc, "winerror", None) == 10048
        )
        if busy:
            print("")
            print("================================================")
            print("  Port %s busy" % port)
            print("================================================")
            print("  Another GroveLink (or app) is already using")
            print("  TCP port %s on this PC." % port)
            print("")
            print("  Fix: close the other GroveLink bridge window,")
            print("  or change [server] port= in config.ini, then")
            print("  run START_GROVELINK again.")
            print("================================================")
            sys.stdout.flush()
            return
        print("Could not start bridge on port %s:" % port, exc)
        sys.stdout.flush()
        return

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
