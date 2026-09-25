"""Password login, in-memory sessions, and per-IP lockout."""

import hmac
import html
import secrets
import time

COOKIE = "peekin_session"
SESSION_TTL = 12 * 3600
MAX_FAILURES = 5
BASE_LOCK = 60
MAX_LOCK = 3600


class Auth:
    # ponytail: all state in memory for one process; a restart logs everyone out.
    def __init__(self, password: str | None, clock=time.monotonic):
        self.password = password
        self.clock = clock
        self.sessions: dict[str, float] = {}  # token -> expiry
        self.failures: dict[str, int] = {}
        self.locked_until: dict[str, float] = {}
        self.last_lock: dict[str, int] = {}

    @property
    def enabled(self) -> bool:
        return self.password is not None

    def check(self, token: str | None) -> bool:
        if not self.enabled:
            return True
        expiry = self.sessions.get(token or "")
        if expiry is None:
            return False
        if expiry <= self.clock():
            self.sessions.pop(token, None)
            return False
        return True

    def locked_for(self, ip: str) -> float:
        return max(0.0, self.locked_until.get(ip, 0.0) - self.clock())

    def attempt(self, ip: str, password: str) -> str | None:
        """Return a new session token on success; None on failure or while locked."""
        if self.locked_for(ip):
            return None
        now = self.clock()
        if hmac.compare_digest(password.encode(), self.password.encode()):
            for state in (self.failures, self.locked_until, self.last_lock):
                state.pop(ip, None)
            self.sessions = {t: e for t, e in self.sessions.items() if e > now}
            token = secrets.token_urlsafe(32)
            self.sessions[token] = now + SESSION_TTL
            return token
        failures = self.failures.get(ip, 0) + 1
        if failures >= MAX_FAILURES:
            lock = min(self.last_lock.get(ip, BASE_LOCK // 2) * 2, MAX_LOCK)
            self.last_lock[ip] = lock
            self.locked_until[ip] = now + lock
            failures = 0
        self.failures[ip] = failures
        return None

    def logout(self, token: str | None) -> None:
        self.sessions.pop(token or "", None)


def login_page(error: str | None = None) -> str:
    message = f'<p class="error" role="alert">{html.escape(error)}</p>' if error else ""
    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="color-scheme" content="light dark">
<title>peekin - log in</title>
<link rel="stylesheet" href="/static/app.css">
</head>
<body>
<form class="login" method="post" action="/login">
<h1>peekin</h1>
{message}
<input type="password" name="password" placeholder="Password" aria-label="Password" autocomplete="current-password" autofocus required>
<button type="submit">Log in</button>
</form>
</body>
</html>
"""
