import pytest


@pytest.fixture
def tree(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "a.txt").write_text("hello")
    (root / "code.py").write_text("def f():\n    return 1\n")
    (root / "page.html").write_text("<script>alert(1)</script>")
    (root / "doc.pdf").write_bytes(b"%PDF-1.4\n%%EOF\n")
    (root / "photo.jpg").write_bytes(b"not really a jpeg")
    (root / "sub").mkdir()
    (root / "sub" / "b.txt").write_text("b")
    (root / ".secret").write_text("s")
    (tmp_path / "outside.txt").write_text("outside")
    (root / "escape").symlink_to(tmp_path / "outside.txt")
    return root
