from peekin.auth import BASE_LOCK, MAX_FAILURES, SESSION_TTL, Auth, login_page


class Clock:
    def __init__(self):
        self.t = 1000.0

    def __call__(self):
        return self.t


def test_disabled_auth_accepts_anything():
    assert Auth(None).enabled is False
    assert Auth(None).check(None) is True


def test_login_creates_session_that_expires():
    clock = Clock()
    auth = Auth("pw", clock=clock)
    token = auth.attempt("1.2.3.4", "pw")
    assert token and auth.check(token)
    clock.t += SESSION_TTL + 1
    assert not auth.check(token)


def test_wrong_password_and_bad_tokens():
    auth = Auth("pw")
    assert auth.attempt("ip", "nope") is None
    assert not auth.check(None)
    assert not auth.check("forged")


def test_lockout_after_max_failures_then_doubles():
    clock = Clock()
    auth = Auth("pw", clock=clock)
    for _ in range(MAX_FAILURES):
        auth.attempt("ip", "x")
    assert auth.locked_for("ip") == BASE_LOCK
    assert auth.attempt("ip", "pw") is None  # right password refused while locked
    assert auth.locked_for("other-ip") == 0
    clock.t += BASE_LOCK
    for _ in range(MAX_FAILURES):
        auth.attempt("ip", "x")
    assert auth.locked_for("ip") == 2 * BASE_LOCK


def test_success_resets_failures():
    auth = Auth("pw", clock=Clock())
    for _ in range(MAX_FAILURES - 1):
        auth.attempt("ip", "x")
    assert auth.attempt("ip", "pw")
    for _ in range(MAX_FAILURES - 1):
        auth.attempt("ip", "x")
    assert auth.locked_for("ip") == 0


def test_logout_drops_session():
    auth = Auth("pw")
    token = auth.attempt("ip", "pw")
    auth.logout(token)
    assert not auth.check(token)


def test_non_ascii_password():
    auth = Auth("p\u00e4ss")
    assert auth.attempt("ip", "p\u00e4ss")


def test_login_page_escapes_error():
    page = login_page("<b>bad</b>")
    assert "&lt;b&gt;bad&lt;/b&gt;" in page and 'name="password"' in page
