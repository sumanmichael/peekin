import os

import pytest

Image = pytest.importorskip("PIL.Image")

from starlette.testclient import TestClient  # noqa: E402

from peekin.app import create_app  # noqa: E402
from peekin.auth import Auth  # noqa: E402
from peekin.fs import Root  # noqa: E402
from peekin.thumbs import SIZE, Thumbs  # noqa: E402


@pytest.fixture
def thumbs(tmp_path):
    return Thumbs(tmp_path / "cache")


def make_jpeg(path, size=(800, 600)):
    Image.new("RGB", size, "red").save(path, "JPEG")


def test_thumbnail_created_and_cached(tree, thumbs):
    make_jpeg(tree / "big.jpg")
    first = thumbs.get(tree / "big.jpg")
    assert first.parent == thumbs.cache_dir
    with Image.open(first) as im:
        assert im.format == "WEBP" and max(im.size) == SIZE
    stamp = first.stat().st_mtime_ns
    assert thumbs.get(tree / "big.jpg") == first
    assert first.stat().st_mtime_ns == stamp


def test_changed_file_gets_new_thumbnail(tree, thumbs):
    make_jpeg(tree / "x.jpg")
    a = thumbs.get(tree / "x.jpg")
    make_jpeg(tree / "x.jpg", (400, 900))
    os.utime(tree / "x.jpg", ns=(1, 1))
    assert thumbs.get(tree / "x.jpg") != a


def test_thumb_route_and_folder_untouched(tree, thumbs):
    make_jpeg(tree / "big.jpg")
    before = sorted(os.listdir(tree))
    c = TestClient(create_app(Root(tree), Auth(None), thumbs))
    r = c.get("/thumb?path=big.jpg")
    assert r.status_code == 200 and r.headers["content-type"] == "image/webp"
    assert c.get("/thumb?path=photo.jpg").status_code == 404  # not a real image
    assert c.get("/thumb?path=../outside.txt").status_code == 404
    assert c.get("/api/list").json()["thumbs"] is True
    assert sorted(os.listdir(tree)) == before


def test_thumb_route_off_without_flag(client):
    assert client.get("/thumb?path=photo.jpg").status_code == 404
