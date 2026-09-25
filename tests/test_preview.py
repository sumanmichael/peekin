from peekin.preview import MAX_BYTES, code_preview


def test_highlights_python(tmp_path):
    p = tmp_path / "x.py"
    p.write_text("def f():\n    return 1\n")
    out = code_preview(p)
    assert out["binary"] is False and out["truncated"] is False
    assert 'class="hl' in out["html"] and '<span class="k">def</span>' in out["html"]


def test_binary_detected(tmp_path):
    p = tmp_path / "x.dat"
    p.write_bytes(b"abc\x00def")
    assert code_preview(p) == {"binary": True, "truncated": False, "html": ""}


def test_large_file_truncated_and_escaped(tmp_path):
    p = tmp_path / "big.txt"
    p.write_bytes(b"<b>" + b"a" * MAX_BYTES)
    out = code_preview(p)
    assert out["truncated"] is True
    assert out["html"].startswith('<pre class="plain">&lt;b&gt;')


def test_unknown_extension_escapes_as_text(tmp_path):
    p = tmp_path / "notes.zzz"
    p.write_text("<script>")
    assert "&lt;script&gt;" in code_preview(p)["html"]


def test_invalid_utf8_replaced(tmp_path):
    p = tmp_path / "x.txt"
    p.write_bytes(b"caf\xe9")
    assert "�" in code_preview(p)["html"]
