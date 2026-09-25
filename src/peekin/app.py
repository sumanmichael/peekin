"""Starlette app: routes, login guard, and security headers."""

import math
from pathlib import Path
from urllib.parse import parse_qs

from starlette.applications import Starlette
from starlette.datastructures import MutableHeaders
from starlette.exceptions import HTTPException
from starlette.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from starlette.routing import Mount, Route
from starlette.staticfiles import StaticFiles

from .auth import COOKIE, SESSION_TTL, Auth, login_page
from .fs import NotFound, Root
from .preview import code_preview

STATIC = Path(__file__).parent / "static"
APP_CSP = "default-src 'self'; img-src 'self' blob:; media-src 'self'; frame-src 'self'; object-src 'self'"
ATTACHMENT = {".html", ".htm", ".svg", ".xml", ".xhtml"}
MAX_FORM = 4096


def hostname(host: str) -> str:
    """Strip the port from a Host header value, handling [IPv6]:port."""
    if host.startswith("["):
        return host[1:host.find("]")]
    return host.rsplit(":", 1)[0] if host.count(":") == 1 else host


class Hardening:
    """Adds security headers to every response and optionally enforces a Host allow-list."""

    def __init__(self, app, allowed_hosts: set[str] | None = None):
        self.app = app
        self.allowed_hosts = allowed_hosts

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        if self.allowed_hosts is not None:
            host = dict(scope["headers"]).get(b"host", b"").decode("latin-1")
            if hostname(host) not in self.allowed_hosts:
                return await Response("invalid host", 400)(scope, receive, send)
        is_raw = scope["path"] == "/raw"

        async def send_with_headers(message):
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                headers.setdefault("X-Content-Type-Options", "nosniff")
                headers.setdefault("Referrer-Policy", "no-referrer")
                if not is_raw:  # /raw sets its own policy (none for PDF)
                    headers.setdefault("Content-Security-Policy", APP_CSP)
            await send(message)

        await self.app(scope, receive, send_with_headers)


def create_app(root: Root, auth: Auth, thumbs=None, allowed_hosts: set[str] | None = None) -> Starlette:
    def logged_in(request) -> bool:
        return auth.check(request.cookies.get(COOKIE))

    def require(request) -> None:
        if not logged_in(request):
            raise HTTPException(401, "login required")

    def resolve_file(request) -> Path:
        try:
            path = root.resolve(request.query_params.get("path", ""))
        except NotFound:
            raise HTTPException(404, "not found") from None
        if not path.is_file():  # directories, FIFOs, devices
            raise HTTPException(400, "not a regular file")
        return path

    def index(request):
        if not logged_in(request):
            return RedirectResponse("/login", 303)
        return FileResponse(STATIC / "index.html")

    def login_get(request):
        if not auth.enabled:
            return RedirectResponse("/", 303)
        return HTMLResponse(login_page())

    async def login_post(request):
        if not auth.enabled:
            return RedirectResponse("/", 303)
        ip = request.client.host if request.client else "unknown"
        wait = auth.locked_for(ip)
        if wait:
            return HTMLResponse(login_page(f"Too many attempts. Try again in {math.ceil(wait)} s."), 429)
        body = b""
        async for chunk in request.stream():
            body += chunk
            if len(body) > MAX_FORM:
                return HTMLResponse(login_page("Request too large."), 413)
        password = parse_qs(body.decode("utf-8", "replace")).get("password", [""])[0]
        token = auth.attempt(ip, password)
        if token is None:
            return HTMLResponse(login_page("Wrong password."), 401)
        response = RedirectResponse("/", 303)
        response.set_cookie(COOKIE, token, max_age=SESSION_TTL, path="/", httponly=True, samesite="strict")
        return response

    def logout(request):
        auth.logout(request.cookies.get(COOKIE))
        response = RedirectResponse("/login" if auth.enabled else "/", 303)
        response.delete_cookie(COOKIE, path="/")
        return response

    def api_list(request):
        require(request)
        try:
            entries = root.listdir(request.query_params.get("path", ""))
        except NotFound:
            raise HTTPException(404, "not found") from None
        except NotADirectoryError:
            raise HTTPException(400, "not a directory") from None
        return JSONResponse({"root": root.path.name, "auth": auth.enabled, "thumbs": thumbs is not None, "entries": entries})

    def api_code(request):
        require(request)
        return JSONResponse(code_preview(resolve_file(request)))

    def raw(request):
        require(request)
        path = resolve_file(request)
        suffix = path.suffix.lower()
        headers = {} if suffix == ".pdf" else {"Content-Security-Policy": "sandbox"}
        attach = suffix in ATTACHMENT or "download" in request.query_params
        return FileResponse(path, headers=headers, filename=path.name,
                            content_disposition_type="attachment" if attach else "inline")

    def thumb(request):
        require(request)
        if thumbs is None:
            raise HTTPException(404, "not found")
        path = resolve_file(request)
        try:
            out = thumbs.get(path)
        except Exception:  # Pillow raises many error types for unsupported or broken images
            raise HTTPException(404, "not found") from None
        return FileResponse(out, media_type="image/webp", headers={"Cache-Control": "private, max-age=86400"})

    async def http_error(request, exc):
        return JSONResponse({"error": exc.detail}, exc.status_code, headers=exc.headers)

    app = Starlette(
        routes=[
            Route("/", index),
            Route("/favicon.ico", lambda request: Response(status_code=204)),  # no icon; avoids a console 404
            Route("/login", login_get, methods=["GET"]),
            Route("/login", login_post, methods=["POST"]),
            Route("/logout", logout, methods=["POST"]),
            Route("/api/list", api_list),
            Route("/api/code", api_code),
            Route("/raw", raw),
            Route("/thumb", thumb),
            Mount("/static", StaticFiles(directory=STATIC)),
        ],
        exception_handlers={HTTPException: http_error},
    )
    app.add_middleware(Hardening, allowed_hosts=allowed_hosts)
    return app
