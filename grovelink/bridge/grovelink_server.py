# GroveLink bridge — Windows 7, Python 2.7 or 3.4-3.8, stdlib only
from __future__ import print_function

import json
import os
import shutil
import socket
import sys
import threading
import time

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


def _mkdir(path):
    if not path or os.path.isdir(path):
        return
    try:
        os.makedirs(path)
    except Exception:
        pass


def ensure_gallery_dirs(cfg, gta_dir):
    """Create expected Gallery folders so detect_gallery can find them later."""
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
        os.path.join(gta_dir or "", "Gallery") if gta_dir else "",
        os.path.join(gta_dir or "", "User Files", "Gallery") if gta_dir else "",
    ]
    for path in candidates:
        if path:
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


def stamp_now():
    now = time.time()
    STATE["last_refresh"] = int(now)
    STATE["last_refresh_human"] = human_time(now)
    return now


def list_images(folders):
    out = []
    seen = set()
    for folder in folders:
        if not folder or not os.path.isdir(folder):
            continue
        try:
            names = os.listdir(folder)
        except Exception:
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
    return out


def copy_latest(folders):
    images = list_images(folders)
    copied = []
    for mtime, full, name in images[:40]:
        dest_name = "%d_%s" % (int(mtime), name.replace(" ", "_"))
        dest = os.path.join(WEB_PHOTOS, dest_name)
        if not os.path.isfile(dest):
            try:
                shutil.copy2(full, dest)
            except Exception:
                continue
        copied.append({
            "file": dest_name,
            "mtime": int(mtime),
            "when": human_time(mtime),
        })
    STATE["photos"] = copied
    stamp_now()
    return copied


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
  .copybtn {
    flex:0 0 auto; background:#1a3; color:#d7ffd0; border:1px solid #2cff6a;
    padding:10px 12px; font-size:13px; font-weight:bold; min-height:44px; cursor:pointer;
  }
  .status { margin-top:8px; font-size:11px; color:#7aaa7a; }
  .status .ok { color:#2cff6a; }
  .status .bad { color:#ff6a6a; }
  .pulse { display:inline-block; width:8px; height:8px; border-radius:50%; background:#2cff6a; margin-right:6px; }
  .pulse.dim { background:#445; }
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
  .shot { margin:12px; background:#000; border:1px solid #1a4; }
  .shot a { display:block; }
  .shot img { width:100%; display:block; cursor:zoom-in; }
  .meta { padding:6px 10px; font-size:11px; color:#7aaa7a; }
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
</style>
</head>
<body>
<div class=\"shell\">
  <header>
    <h1>GROVELINK</h1>
    <div class=\"sub\">Live from GTA San Andreas &nbsp;·&nbsp; <span id=\"count\">0</span> shots</div>
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
    <div class=\"status\">
      <span class=\"pulse\" id=\"pulse\"></span>
      Bridge: <span id=\"bridge_status\" class=\"ok\">online</span>
      &nbsp;·&nbsp; Last refresh: <span id=\"last_refresh\">—</span>
      &nbsp;·&nbsp; <span id=\"refresh_hint\">auto every 2s</span>
    </div>
  </header>
  <form id=\"f\">
    <input id=\"msg\" type=\"text\" maxlength=\"80\" placeholder=\"Message to CJ...\" required>
    <button class=\"send\" type=\"submit\">SEND</button>
  </form>
  <div class=\"okmsg\" id=\"ok\"></div>
  <div id=\"feed\"></div>
</div>
<div id=\"lightbox\" onclick=\"closeLb(event)\">
  <button type=\"button\" class=\"close\" onclick=\"closeLb(event)\">&times;</button>
  <img id=\"lbimg\" src=\"\" alt=\"full size\">
</div>
<script>
var EMPTY_HTML =
  '<div class=\"empty\">' +
  '<h2>NO PHOTOS YET</h2>' +
  '<ol>' +
  '<li>Run <b>GroveLink Phone</b> / <b>START_GROVELINK</b> on the PC (keep the window open).</li>' +
  '<li>In GTA press <b>K</b> to open the phone.</li>' +
  '<li>Select <b>Camera</b>, then <b>Enter</b> or <b>Space</b>.</li>' +
  '<li>Phone and PC must be on the <b>same Wi-Fi</b>.</li>' +
  '</ol>' +
  '</div>';

function escapeHtml(s) {
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
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

function paint(data) {
  var feed = document.getElementById('feed');
  var count = document.getElementById('count');
  var photos = data.photos || [];
  count.textContent = photos.length;
  var lr = data.last_refresh_human || data.last_refresh || '—';
  document.getElementById('last_refresh').textContent = lr;
  var st = document.getElementById('bridge_status');
  var pulse = document.getElementById('pulse');
  if (data.ok === false) {
    st.textContent = 'offline?';
    st.className = 'bad';
    pulse.className = 'pulse dim';
  } else {
    st.textContent = 'online';
    st.className = 'ok';
    pulse.className = 'pulse';
  }
  if (data.lan_url) document.getElementById('lan_url').textContent = data.lan_url;
  if (data.local_url) document.getElementById('local_url').textContent = data.local_url;
  if (!photos.length) {
    feed.innerHTML = EMPTY_HTML;
    return;
  }
  var html = '';
  for (var i = 0; i < photos.length && i < 20; i++) {
    var p = photos[i];
    var name = p.file || p;
    var when = p.when || '';
    var href = '/photo/' + name;
    html += '<div class=\"shot\">';
    html += '<a href=\"' + href + '\" target=\"_blank\" rel=\"noopener\" onclick=\"openLb(\\'' + href + '\\'); return false;\">';
    html += '<img src=\"' + href + '\" alt=\"shot\">';
    html += '</a>';
    html += '<div class=\"meta\">' + escapeHtml(when ? when + ' · ' + name : name) +
            ' · <a href=\"' + href + '\" target=\"_blank\" rel=\"noopener\">full size</a></div>';
    html += '</div>';
  }
  feed.innerHTML = html;
}
function poll() {
  var x = new XMLHttpRequest();
  x.open('GET', '/api', true);
  x.onreadystatechange = function() {
    if (x.readyState === 4 && x.status === 200) {
      try { paint(JSON.parse(x.responseText)); } catch (e) {}
      var hint = document.getElementById('refresh_hint');
      if (hint) {
        hint.textContent = 'updated';
        setTimeout(function(){ hint.textContent = 'auto every 2s'; }, 800);
      }
    }
  };
  x.send();
}
document.getElementById('copy_lan').onclick = function() {
  copyText(document.getElementById('lan_url').textContent, this);
};
document.getElementById('copy_local').onclick = function() {
  copyText(document.getElementById('local_url').textContent, this);
};
document.getElementById('f').onsubmit = function(ev) {
  ev.preventDefault();
  var msg = document.getElementById('msg').value;
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
};
document.getElementById('feed').innerHTML = EMPTY_HTML;
poll();
setInterval(poll, 2000);
</script>
</body>
</html>
"""


def render_html():
    lan = "http://%s:%s" % (STATE.get("ip", "127.0.0.1"), STATE.get("port", 8088))
    local = "http://127.0.0.1:%s" % STATE.get("port", 8088)
    return (
        HTML_TEMPLATE
        .replace("__LAN_URL__", lan)
        .replace("__LOCAL_URL__", local)
    )


def api_payload():
    ip = STATE.get("ip", "127.0.0.1")
    port = STATE.get("port", 8088)
    return {
        "ok": True,
        "photos": STATE.get("photos", []),
        "inbox": STATE.get("inbox", []),
        "photo_count": len(STATE.get("photos", [])),
        "last_refresh": STATE.get("last_refresh", 0),
        "last_refresh_human": STATE.get("last_refresh_human", ""),
        "lan_url": "http://%s:%s" % (ip, port),
        "local_url": "http://127.0.0.1:%s" % port,
        "ip": ip,
        "port": port,
    }


def health_payload():
    return {
        "ok": True,
        "photo_count": len(STATE.get("photos", [])),
        "galleries": list(STATE.get("galleries", [])),
        "ip": STATE.get("ip", "127.0.0.1"),
        "port": STATE.get("port", 8088),
        "gta_dir": STATE.get("gta_dir", "") or "",
    }


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
        if path == "/" or path == "/index.html":
            self._html(render_html())
            return
        if path == "/api":
            self._json(api_payload())
            return
        if path == "/health":
            self._json(health_payload())
            return
        if path.startswith("/photo/"):
            name = os.path.basename(unquote(path[len("/photo/"):]))
            full = os.path.join(WEB_PHOTOS, name)
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
        if self.path.split("?", 1)[0] != "/send":
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0") or 0)
        raw = self.rfile.read(length) if length else b""
        try:
            text = raw.decode("utf-8")
        except Exception:
            text = raw.decode("latin-1")
        msg = ""
        if text.lstrip().startswith("{"):
            try:
                msg = json.loads(text).get("msg") or ""
            except Exception:
                msg = ""
        else:
            fields = parse_qs(text)
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
        except Exception as exc:
            print("watch error:", exc)
        # Idle poll: 1s normally; stay responsive
        time.sleep(1.0)


def main():
    cfg = read_cfg()
    gta_dir = detect_gta_dir(cfg)
    ensure_dirs(cfg, gta_dir)
    galleries = detect_gallery(cfg, gta_dir)
    ini = link_ini_path(gta_dir)
    port = 8088
    try:
        port = int(cfg_get(cfg, "server", "port", "8088") or "8088")
    except Exception:
        port = 8088

    ip = lan_ip()
    STATE["ip"] = ip
    STATE["port"] = port
    STATE["gta_dir"] = gta_dir or ""
    STATE["galleries"] = list(galleries)
    STATE["bridge_ok"] = True

    print("================================================")
    print("  GROVELINK PHONE BRIDGE")
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
