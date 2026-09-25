"""Command-line entry point: parse options, bind the socket, run uvicorn."""

import argparse
import errno
import os
import secrets
import socket
import sys
import webbrowser
from pathlib import Path

import uvicorn

from . import __version__
from .app import create_app
from .auth import Auth
from .fs import Root

LOOPBACK = {"127.0.0.1", "::1", "localhost"}
THUMBS_HINT = "uvx --from 'peekin[thumbs]' peekin --thumbs"


def resolve_password(host, env, password_file, no_password):
    """Return (password or None, whether it was generated)."""
    password = env.get("PEEKIN_PASSWORD") or None
    if password is None and password_file is not None:
        lines = Path(password_file).read_text().splitlines()
        password = lines[0].strip() if lines else ""
        if not password:
            raise ValueError(f"password file is empty: {password_file}")
    if no_password:
        if password is not None:
            raise ValueError("--no-password conflicts with PEEKIN_PASSWORD / --password-file")
        return None, False
    if password is not None:
        return password, False
    if host in LOOPBACK:
        return None, False
    return secrets.token_urlsafe(12), True


def bind(host: str, port: int) -> socket.socket:
    sock = socket.socket(socket.AF_INET6 if ":" in host else socket.AF_INET, socket.SOCK_STREAM)
    try:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.bind((host, port))
    except OSError:
        sock.close()
        raise
    return sock


def lan_ip() -> str | None:
    with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as s:
        try:
            s.connect(("10.255.255.255", 1))  # sends nothing; just picks the outbound interface
            return s.getsockname()[0]
        except OSError:
            return None


def urls(host: str, port: int) -> list[str]:
    names = ["127.0.0.1", lan_ip()] if host in ("0.0.0.0", "::") else [host]
    return [f"http://[{n}]:{port}" if ":" in n else f"http://{n}:{port}" for n in names if n]


def cache_dir() -> Path:
    return Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache") / "peekin" / "thumbs"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="peekin", description="Browse and preview a folder in your web browser (read-only).")
    parser.add_argument("folder", nargs="?", default=".", help="folder to share (default: current folder)")
    parser.add_argument("--host", default="127.0.0.1", help="address to listen on; 0.0.0.0 for your network (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="port to listen on (default: 8000)")
    parser.add_argument("--password-file", type=Path, help="read the password from this file's first line (or set PEEKIN_PASSWORD)")
    parser.add_argument("--no-password", action="store_true", help="never require a password, even on the network")
    parser.add_argument("--thumbs", action="store_true", help="image thumbnails in grid view (needs peekin[thumbs])")
    parser.add_argument("--show-hidden", action="store_true", help="show dotfiles and dot-folders")
    parser.add_argument("--open", action="store_true", help="open the browser after starting")
    parser.add_argument("--version", action="version", version=f"peekin {__version__}")
    args = parser.parse_args(argv)

    folder = Path(args.folder).expanduser()
    if not folder.is_dir():
        parser.error(f"not a folder: {folder}")
    try:
        password, generated = resolve_password(args.host, os.environ, args.password_file, args.no_password)
    except (ValueError, OSError) as e:
        parser.error(str(e))

    thumbs = None
    if args.thumbs:
        try:
            from .thumbs import Thumbs
        except ImportError:
            print(f"error: --thumbs needs Pillow. Run: {THUMBS_HINT}", file=sys.stderr)
            return 1
        thumbs = Thumbs(cache_dir())

    try:
        sock = bind(args.host, args.port)
    except OSError as e:
        reason = "already in use" if e.errno == errno.EADDRINUSE else e.strerror
        print(f"error: cannot listen on {args.host}:{args.port} ({reason})", file=sys.stderr)
        return 1

    allowed = LOOPBACK if password is None and args.host in LOOPBACK else None
    app = create_app(Root(folder, args.show_hidden), Auth(password), thumbs, allowed_hosts=allowed)
    links = urls(args.host, sock.getsockname()[1])
    print(f"peekin {__version__} serving {folder.resolve()}")
    for link in links:
        print(f"  {link}")
    if generated:
        print(f"  password: {password}")
    elif password is None and args.host not in LOOPBACK:
        print("warning: no password; anyone on your network can read this folder", file=sys.stderr)
    if args.open:
        webbrowser.open(links[0])
    sys.stdout.flush()  # banner must show even when stdout is a pipe (e.g. a log file)
    uvicorn.Server(uvicorn.Config(app, log_level="warning")).run(sockets=[sock])
    return 0
