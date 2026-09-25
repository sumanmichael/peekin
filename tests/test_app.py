import os

from starlette.testclient import TestClient

from peekin.app import create_app, hostname
from peekin.auth import MAX_FAILURES, Auth
from peekin.fs import Root


def test_index_and_list(client):
    assert client.get("/").status_code == 200
    data = client.get("/api/list").json()
    assert data["auth"] is False and data["thumbs"] is False and data["root"] == "root"
    assert data["entries"][0]["name"] == "sub"


def test_list_errors(client):
    assert client.get("/api/list?path=..").status_code == 404
    assert client.get("/api/list?path=%2e%2e%2foutside.txt").status_code == 404
    assert client.get("/api/list?path=a.txt").status_code == 400
    assert client.get("/api/list?path=nope").json() == {"error": "not found"}


def test_security_headers(client):
    r = client.get("/")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert r.headers["referrer-policy"] == "no-referrer"
    assert "default-src 'self'" in r.headers["content-security-policy"]


def test_raw_range(client):
    r = client.get("/raw?path=a.txt", headers={"Range": "bytes=1-3"})
    assert r.status_code == 206 and r.content == b"ell"


def test_head_raw(client):
    r = client.head("/raw?path=a.txt")
    assert r.status_code == 200 and r.headers["content-length"] == "5"


def test_raw_sandbox_and_disposition(client):
    r = client.get("/raw?path=page.html")
    assert r.headers["content-security-policy"] == "sandbox"
    assert r.headers["content-disposition"].startswith("attachment")
    assert r.headers["x-content-type-options"] == "nosniff"
    assert "content-security-policy" not in client.get("/raw?path=doc.pdf").headers
    assert client.get("/raw?path=a.txt").headers["content-disposition"].startswith("inline")
    assert client.get("/raw?path=a.txt&download=1").headers["content-disposition"].startswith("attachment")


def test_raw_rejects(client):
    assert client.get("/raw?path=sub").status_code == 400
    assert client.get("/raw?path=escape").status_code == 404
    assert client.get("/raw?path=.secret").status_code == 404


def test_code_preview(client):
    assert '<span class="k">def</span>' in client.get("/api/code?path=code.py").json()["html"]


def test_write_methods_rejected(client):
    assert client.post("/raw?path=a.txt").status_code == 405
    assert client.delete("/api/list").status_code == 405


def test_special_characters_in_names(tree, client):
    (tree / "a #1 %?&.txt").write_text("odd")
    assert client.get("/raw", params={"path": "a #1 %?&.txt"}).content == b"odd"


def test_fifo_is_rejected(tree, client):
    os.mkfifo(tree / "pipe")
    assert client.get("/raw?path=pipe").status_code == 400
    assert client.get("/api/code?path=pipe").status_code == 400


def test_requires_login(locked_client):
    assert locked_client.get("/api/list").status_code == 401
    assert locked_client.get("/raw?path=a.txt").status_code == 401
    assert locked_client.get("/api/code?path=code.py").status_code == 401
    r = locked_client.get("/", follow_redirects=False)
    assert r.status_code == 303 and r.headers["location"] == "/login"
    assert locked_client.get("/login").status_code == 200
    assert locked_client.get("/static/app.css").status_code == 200


def test_login_flow(locked_client):
    r = locked_client.post("/login", data={"password": "s3cret"}, follow_redirects=False)
    assert r.status_code == 303
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "max-age=43200" in cookie
    assert locked_client.get("/api/list").json()["auth"] is True
    locked_client.post("/logout")
    assert locked_client.get("/api/list").status_code == 401


def test_wrong_password_then_lockout(locked_client):
    for _ in range(MAX_FAILURES):
        assert locked_client.post("/login", data={"password": "no"}).status_code == 401
    assert locked_client.post("/login", data={"password": "s3cret"}).status_code == 429


def test_oversized_login_body(locked_client):
    assert locked_client.post("/login", data={"password": "x" * 5000}).status_code == 413


def test_login_redirects_when_auth_disabled(client):
    assert client.get("/login", follow_redirects=False).status_code == 303


def test_host_allow_list(tree):
    app = create_app(Root(tree), Auth(None), allowed_hosts={"127.0.0.1", "localhost", "::1"})
    c = TestClient(app, base_url="http://127.0.0.1:8000")
    assert c.get("/api/list").status_code == 200
    assert c.get("/api/list", headers={"Host": "evil.example"}).status_code == 400
    assert c.get("/api/list", headers={"Host": "[::1]:8000"}).status_code == 200


def test_hostname():
    assert hostname("127.0.0.1:8000") == "127.0.0.1"
    assert hostname("[::1]:8000") == "::1"
    assert hostname("localhost") == "localhost"
