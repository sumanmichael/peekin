import socket
import sys

import pytest

from peekin.cli import main, resolve_password


def test_loopback_without_password_has_no_login():
    assert resolve_password("127.0.0.1", {}, None, False) == (None, False)


def test_lan_without_password_generates_one():
    password, generated = resolve_password("0.0.0.0", {}, None, False)
    assert generated is True and len(password) >= 16


def test_env_password_wins_over_file(tmp_path):
    f = tmp_path / "pw"
    f.write_text("fromfile\n")
    assert resolve_password("0.0.0.0", {"PEEKIN_PASSWORD": "fromenv"}, f, False) == ("fromenv", False)


def test_password_file_first_line_stripped(tmp_path):
    f = tmp_path / "pw"
    f.write_text("  secret \nignored\n")
    assert resolve_password("127.0.0.1", {}, f, False) == ("secret", False)


def test_empty_password_file_is_error(tmp_path):
    f = tmp_path / "pw"
    f.write_text("\n")
    with pytest.raises(ValueError):
        resolve_password("127.0.0.1", {}, f, False)


def test_no_password_conflicts_with_source():
    with pytest.raises(ValueError):
        resolve_password("0.0.0.0", {"PEEKIN_PASSWORD": "x"}, None, True)


def test_no_password_on_lan():
    assert resolve_password("0.0.0.0", {}, None, True) == (None, False)


def test_missing_folder_exits_2(tmp_path):
    with pytest.raises(SystemExit) as exc:
        main([str(tmp_path / "nope")])
    assert exc.value.code == 2


def test_no_password_with_env_exits_2(tmp_path, monkeypatch):
    monkeypatch.setenv("PEEKIN_PASSWORD", "x")
    with pytest.raises(SystemExit) as exc:
        main([str(tmp_path), "--no-password"])
    assert exc.value.code == 2


def test_port_in_use_returns_1(tmp_path, capsys):
    with socket.socket() as busy:
        busy.bind(("127.0.0.1", 0))
        busy.listen()
        port = busy.getsockname()[1]
        assert main([str(tmp_path), "--port", str(port)]) == 1
    assert "already in use" in capsys.readouterr().err


def test_thumbs_without_pillow_returns_1(tmp_path, monkeypatch, capsys):
    monkeypatch.setitem(sys.modules, "PIL", None)
    monkeypatch.delitem(sys.modules, "peekin.thumbs", raising=False)
    assert main([str(tmp_path), "--thumbs"]) == 1
    assert "peekin[thumbs]" in capsys.readouterr().err


def test_banner_visible_through_pipe_while_running(tmp_path):
    import subprocess
    import threading

    proc = subprocess.Popen(
        [sys.executable, "-m", "peekin", str(tmp_path), "--host", "0.0.0.0", "--port", "0"],
        stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
    )
    lines = []

    def read_until_password():
        for line in proc.stdout:
            lines.append(line)
            if line.strip().startswith("password: "):
                return

    reader = threading.Thread(target=read_until_password, daemon=True)
    reader.start()
    reader.join(timeout=10)
    proc.terminate()
    proc.wait(timeout=10)
    assert lines and lines[0].startswith("peekin ")
    assert any(line.strip().startswith("password: ") for line in lines)


@pytest.mark.parametrize("args,env,check_host", [
    (["--host", "0.0.0.0", "--no-password"], {}, True),
    ([], {}, True),
    (["--host", "0.0.0.0"], {"PEEKIN_PASSWORD": "pw"}, False),
])
def test_server_wiring(tmp_path, monkeypatch, args, env, check_host):
    import uvicorn

    import peekin.cli as cli

    seen = {}
    real_create_app = cli.create_app
    monkeypatch.setattr(cli, "create_app", lambda *a, **kw: seen.update(kw) or real_create_app(*a, **kw))
    monkeypatch.setattr(uvicorn.Server, "run", lambda self, sockets=None: seen.update(config=self.config))
    monkeypatch.delenv("PEEKIN_PASSWORD", raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    assert main([str(tmp_path), "--port", "0", *args]) == 0
    assert seen["check_host"] is check_host
    assert seen["config"].proxy_headers is False  # X-Forwarded-For must not fake the client IP
