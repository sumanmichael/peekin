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


def test_mid_size_file_skips_highlighting(tmp_path):
    p = tmp_path / "big.js"
    p.write_text("var a = 1;\n" * 30_000)  # ~330 KB: highlighted HTML would be many MB
    out = code_preview(p)
    assert out["truncated"] is False and out["html"].startswith('<pre class="plain">')


def test_markdown_renders_gfm_basics(tmp_path):
    from peekin.preview import markdown_preview

    p = tmp_path / "x.md"
    p.write_text("# Title\n\n| a | b |\n|---|---|\n| 1 | 2 |\n\n~~old~~ and [link](other.md)\n")
    html = markdown_preview(p)["html"]
    assert "<h1>Title</h1>" in html and "<table>" in html and "<s>old</s>" in html
    assert '<a href="other.md">link</a>' in html


def test_markdown_escapes_raw_html_and_drops_script_links(tmp_path):
    from peekin.preview import markdown_preview

    p = tmp_path / "x.md"
    p.write_text('<script>alert(1)</script>\n\n<img src=x onerror=alert(1)>\n\n[bad](javascript:alert(1))\n')
    html = markdown_preview(p)["html"]
    assert "<script" not in html and "<img" not in html
    assert "&lt;script&gt;" in html and 'href="javascript' not in html


def test_markdown_fenced_code_is_highlighted(tmp_path):
    from peekin.preview import markdown_preview

    p = tmp_path / "x.md"
    p.write_text("```python\ndef f():\n    pass\n```\n")
    html = markdown_preview(p)["html"]
    assert html.startswith('<pre class="hl"><code>') and '<span class="k">def</span>' in html


def test_large_markdown_falls_back_to_plain_text(tmp_path):
    from peekin.preview import markdown_preview

    p = tmp_path / "big.md"
    p.write_bytes(b"# x\n" + b"a" * MAX_BYTES)
    out = markdown_preview(p)
    assert out["truncated"] is True and out["html"].startswith('<pre class="plain">')
