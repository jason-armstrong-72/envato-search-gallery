#!/usr/bin/env python3
"""A tiny local web server for the gallery pages, so a chat can hand back an http:// link.

Usage:
    gallery_server.py ensure [--dir DIR] [--idle SECONDS]   start it if needed, print the port
    gallery_server.py status [--dir DIR]                    print the port, or "not running"
    gallery_server.py stop   [--dir DIR]                    stop it now
    gallery_server.py run    [--dir DIR] [--idle SECONDS]   run in the foreground (used by ensure)

One server is shared by every session on the machine. It serves DIR (default
~/.cache/envato-gallery) on 127.0.0.1 only, and shuts itself down after --idle seconds
(default 3600) with no request. The pid and port live in DIR/.server.json.

The port is 47615 unless ENVATO_GALLERY_PORT says otherwise, so a link and the browser's saved
settings for a page (such as the light or dark choice) survive the server restarting. If that port
is taken by something else, the OS picks a free one instead.

When it starts it also deletes gallery pages in DIR that are older than 7 days (only pages the
builder made; any other file is left alone).

Standard library only.
"""
import argparse
import json
import os
import re
import signal
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

DEFAULT_DIR = Path.home() / ".cache" / "envato-gallery"
DEFAULT_IDLE = 3600
STATE_NAME = ".server.json"
DEFAULT_PORT = 47615
KEEP_DAYS = 7  # the age rule for gallery pages; build_gallery.prune() uses it through prune()
# What build_gallery.py writes: <slug>.html, whose <title> starts with this text. The file name alone
# is not enough (an option page such as ja-tuner.html has the same shape), so both must match.
PAGE_NAME = re.compile(r"[a-z0-9]+(?:-[a-z0-9]+)*\.html")
PAGE_SIGNATURE = b"<title>Envato results: "


def preferred_port():
    """The port to try first: ENVATO_GALLERY_PORT if it is a valid number, else DEFAULT_PORT."""
    try:
        port = int(os.environ.get("ENVATO_GALLERY_PORT", DEFAULT_PORT))
    except ValueError:
        return DEFAULT_PORT
    return port if 1 <= port <= 65535 else DEFAULT_PORT


def prune(folder):
    """Delete gallery pages older than KEEP_DAYS from the cache folder. Returns how many.

    The only pruning rule: build_gallery.prune() calls this. Only a file the builder made is
    removed, judged by its name and by the title near the top of the page. Other files, such as
    option pages, are left alone.
    """
    cutoff = time.time() - KEEP_DAYS * 86400
    removed = 0
    try:
        pages = list(folder.glob("*.html"))
    except OSError:
        return 0
    for page in pages:
        try:
            if not PAGE_NAME.fullmatch(page.name) or not page.is_file() or page.is_symlink():
                continue
            if page.stat().st_mtime >= cutoff:
                continue
            with page.open("rb") as fh:
                if PAGE_SIGNATURE not in fh.read(1024):
                    continue
            page.unlink()
            removed += 1
        except OSError:
            pass
    return removed


def running_port(directory):
    """The port of a live server for this directory, or None. Checks the pid it answers with,
    so a stale state file, or another program that reused the port, is not mistaken for ours."""
    try:
        state = json.loads((directory / STATE_NAME).read_text())
        url = f"http://127.0.0.1:{state['port']}/{STATE_NAME}"
        with urllib.request.urlopen(url, timeout=2) as resp:
            if json.load(resp).get("pid") == state["pid"]:
                return state["port"]
    except Exception:
        pass
    return None


def ensure(directory, idle):
    port = running_port(directory)
    if port:
        return port
    directory.mkdir(parents=True, exist_ok=True)
    try:
        (directory / STATE_NAME).unlink()
    except FileNotFoundError:
        pass
    detach = (
        {"creationflags": 0x00000008 | 0x00000200}  # DETACHED_PROCESS | CREATE_NEW_PROCESS_GROUP
        if os.name == "nt"
        else {"start_new_session": True}
    )
    subprocess.Popen(
        [sys.executable, str(Path(__file__).resolve()), "run", "--dir", str(directory), "--idle", str(idle)],
        stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, **detach,
    )
    for _ in range(50):  # up to 5 seconds
        time.sleep(0.1)
        port = running_port(directory)
        if port:
            return port
    return None


def run(directory, idle):
    directory.mkdir(parents=True, exist_ok=True)
    prune(directory)
    last_request = [time.time()]

    class Handler(SimpleHTTPRequestHandler):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, directory=str(directory), **kwargs)

        def handle(self):
            last_request[0] = time.time()
            super().handle()

        def log_message(self, *args):
            pass

    try:
        server = ThreadingHTTPServer(("127.0.0.1", preferred_port()), Handler)
    except OSError:  # the port is taken by another program: let the OS pick a free one
        server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    state = {"pid": os.getpid(), "port": server.server_address[1]}
    (directory / STATE_NAME).write_text(json.dumps(state))

    def watchdog():
        while time.time() - last_request[0] < idle:
            time.sleep(min(30, max(1, idle / 10)))
        server.shutdown()

    threading.Thread(target=watchdog, daemon=True).start()
    try:
        server.serve_forever()
    finally:
        try:
            if json.loads((directory / STATE_NAME).read_text()).get("pid") == os.getpid():
                (directory / STATE_NAME).unlink()
        except Exception:
            pass


def stop(directory):
    try:
        pid = json.loads((directory / STATE_NAME).read_text())["pid"]
        os.kill(pid, signal.SIGTERM)
        (directory / STATE_NAME).unlink()
        return True
    except Exception:
        return False


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("command", choices=["ensure", "status", "stop", "run"])
    ap.add_argument("--dir", default=str(DEFAULT_DIR), help="folder to serve")
    ap.add_argument("--idle", type=int, default=DEFAULT_IDLE, help="seconds without a request before it exits")
    args = ap.parse_args()
    directory = Path(args.dir).expanduser()

    if args.command == "run":
        run(directory, args.idle)
    elif args.command == "ensure":
        port = ensure(directory, args.idle)
        if not port:
            sys.exit("error: could not start the local server")
        print(port)
    elif args.command == "status":
        port = running_port(directory)
        print(port if port else "not running")
    else:
        print("stopped" if stop(directory) else "not running")


if __name__ == "__main__":
    main()
