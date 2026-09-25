import os

import pytest

from peekin.fs import NotFound, Root, kind_of


def names(entries):
    return [e["name"] for e in entries]


def test_list_dirs_first_hidden_and_escaping_links_skipped(tree):
    assert names(Root(tree).listdir("")) == ["sub", "a.txt", "code.py", "doc.pdf", "page.html", "photo.jpg"]


def test_list_entry_fields(tree):
    [entry] = Root(tree).listdir("sub")
    assert entry == {"name": "b.txt", "path": "sub/b.txt", "type": "file", "kind": "text", "size": 1, "mtime": entry["mtime"]}
    assert isinstance(entry["mtime"], int)


def test_list_shows_hidden_with_flag(tree):
    assert ".secret" in names(Root(tree, show_hidden=True).listdir(""))


@pytest.mark.parametrize("rel", ["..", "../outside.txt", "sub/../../outside.txt", "/etc/passwd", "a.txt\x00", ".secret", "sub/.x", "escape", "missing.txt"])
def test_resolve_rejects(tree, rel):
    with pytest.raises(NotFound):
        Root(tree).resolve(rel)


def test_resolve_allows_hidden_with_flag(tree):
    assert Root(tree, show_hidden=True).resolve(".secret").name == ".secret"


def test_dotdot_blocked_even_with_hidden_flag(tree):
    with pytest.raises(NotFound):
        Root(tree, show_hidden=True).resolve("../outside.txt")


def test_symlink_inside_root_is_followed(tree):
    (tree / "link.txt").symlink_to(tree / "a.txt")
    assert Root(tree).resolve("link.txt") == (tree / "a.txt").resolve()


def test_list_file_raises_not_a_directory(tree):
    with pytest.raises(NotADirectoryError):
        Root(tree).listdir("a.txt")


def test_broken_symlink_skipped(tree):
    (tree / "dangling").symlink_to(tree / "nope")
    assert "dangling" not in names(Root(tree).listdir(""))


@pytest.mark.skipif(os.geteuid() == 0, reason="root ignores permissions")
def test_unreadable_dir_is_not_found(tree):
    (tree / "sub").chmod(0)
    try:
        with pytest.raises(NotFound):
            Root(tree).listdir("sub")
    finally:
        (tree / "sub").chmod(0o755)


@pytest.mark.parametrize("name,kind", [
    ("x.jpg", "image"), ("x.PNG", "image"), ("x.svg", "image"), ("x.webp", "image"),
    ("x.mp4", "video"), ("x.webm", "video"), ("x.mp3", "audio"), ("x.pdf", "pdf"),
    ("x.py", "code"), ("x.ts", "code"), ("Dockerfile", "code"), ("x.txt", "text"), ("x.bin", "other"),
    ("README.md", "markdown"), ("x.MARKDOWN", "markdown"),
])
def test_kind_of(name, kind):
    assert kind_of(name) == kind
