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

HERE = os.path.dirname(os.path.abspath(__file__))
CFG_PATH = os.path.join(HERE, "config.ini")
WEB_PHOTOS = os.path.join(HERE, "photos")
CHAT_PATH = os.path.join(HERE, "chat.json")
STATE = {"photos": [], "chat": [], "sent": 0}
LOCK = threading.Lock()


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


def detect_gta_dir(cfg):
    hinted = cfg_get(cfg, "paths", "gta_dir")
    candidates = [
        hinted,
        r"E:\\GTA San Andreas",
        r"D:\\GTA San Andreas",
        r"C:\\GTA San Andreas",
        r"C:\\Program Files (x86)\\Rockstar Games\\GTA San Andreas",
        r"C:\\Program Files\\Rockstar Games\\GTA San Andreas",
        r"C:\\Games\\GTA San Andreas",
        r"D:\\Games\\GTA San Andreas",
        r"E:\\Games\\GTA San Andreas",
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
    public = os.environ.get("PUBLIC", r"C:\\Users\\Public")
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


def load_chat():
    if not os.path.isfile(CHAT_PATH):
        return []
    try:
        with open(CHAT_PATH, "r") as f:
            data = json.loads(f.read())
        if isinstance(data, list):
            return data[-80:]
    except Exception:
        return []
    return []


def save_chat(rows):
    try:
        with open(CHAT_PATH, "w") as f:
            f.write(json.dumps(rows[-80:]))
    except Exception:
        pass


def add_chat(who, text):
    text = (text or "").strip()
    if not text:
        return
    with LOCK:
        STATE["chat"].append({"from": who, "text": text[:120], "t": int(time.time())})
        STATE["chat"] = STATE["chat"][-80:]
        save_chat(STATE["chat"])


def ensure_dirs(gta_dir):
    if not os.path.isdir(WEB_PHOTOS):
        os.makedirs(WEB_PHOTOS)
    if not gta_dir:
        return
    folder = os.path.join(gta_dir, "CLEO", "GroveLink")
    if not os.path.isdir(folder):
        try:
            os.makedirs(folder)
        except Exception:
            pass
    ini = link_ini_path(gta_dir)
    if not os.path.isfile(ini):
        try:
            with open(ini, "w") as f:
                f.write("[PHOTO]\ntake=0\ncount=0\n\n[INBOX]\nnew=0\nfrom=REAL PHONE\nmsg=\n\n[OUTBOX]\nnew=0\nmsg=\n\n[STATUS]\nbridge=1\nip=0.0.0.0\n")
        except Exception:
            pass


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
            if not (low.endswith(".jpg") or low.endswith(".jpeg") or low.endswith(".bmp") or low.endswith(".png")):
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
        copied.append({"file": dest_name, "mtime": int(mtime)})
    STATE["photos"] = copied
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

HTML = "CHAT_PAGE_PLACEHOLDER"

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
    def do_GET(self):
        path = self.path.split("?", 1)[0]
        if path == "/" or path == "/index.html":
            self._html(HTML)
            return
        if path == "/api":
            with LOCK:
                payload = json.dumps({"photos": STATE.get("photos", []), "chat": STATE.get("chat", [])})
            data = self._bytes(payload)
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path.startswith("/photo/"):
            name = os.path.basename(unquote(path[len("/photo/"):]))
            full = os.path.join(WEB_PHOTOS, name)
            if not os.path.isfile(full):
                self.send_error(404)
                return
            ext = name.lower().rsplit(".", 1)[-1]
            mime = {"jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "bmp": "image/bmp"}.get(ext, "application/octet-stream")
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
        if text.lstrip().startswith("{ "):
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
            add_chat("PHONE", msg)
            write_ini_kv(self.server.link_ini, "INBOX", {"new": "1", "from": "REAL PHONE", "msg": msg.replace("=", "-")})
            print("SMS -> GTA:", msg)
        data = self._bytes('{"ok":true}')
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

def watcher(galleries, ini):
    last_out = ""
    while True:
        try:
            copy_latest(galleries)
            take = read_ini_key(ini, "PHOTO", "take", "0")
            if take == "1":
                write_ini_kv(ini, "PHOTO", {"take": "0"})
                time.sleep(0.4)
                copy_latest(galleries)
                print("Shutter. Phone page has", len(STATE["photos"]), "shots")
            flag = read_ini_key(ini, "OUTBOX", "new", "0")
            msg = read_ini_key(ini, "OUTBOX", "msg", "")
            if flag == "1" and msg and msg != last_out:
                last_out = msg
                add_chat("CJ", msg)
                write_ini_kv(ini, "OUTBOX", {"new": "0"})
                print("CJ -> phone:", msg)
        except Exception as exc:
            print("watch error:", exc)
        time.sleep(0.8)

def main():
    cfg = read_cfg()
    gta_dir = detect_gta_dir(cfg)
    galleries = detect_gallery(cfg, gta_dir)
    ensure_dirs(gta_dir)
    ini = link_ini_path(gta_dir)
    port = 8088
    try:
        port = int(cfg_get(cfg, "server", "port", "8088") or "8088")
    except Exception:
        port = 8088
    STATE["chat"] = load_chat()
    if not STATE["chat"]:
        add_chat("CJ", "GroveLink on. Text me from this page.")
    print("================================================")
    print("  GROVELINK PHONE BRIDGE")
    print("================================================")
    print("GTA folder :", gta_dir or "(not found — edit config.ini)")
    print("link.ini   :", ini)
    ip = lan_ip()
    print("")
    print("  Open in any browser:")
    print("      http://%s:%s" % (ip, port))
    print("      http://127.0.0.1:%s" % port)
    print("================================================")
    sys.stdout.flush()
    write_ini_kv(ini, "STATUS", {"bridge": "1", "ip": ip})
    copy_latest(galleries)
    t = threading.Thread(target=watcher, args=(galleries, ini))
    t.daemon = True
    t.start()
    server = HTTPServer(("0.0.0.0", port), Handler)
    server.link_ini = ini
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("Stopped.")

if __name__ == "__main__":
    main()
