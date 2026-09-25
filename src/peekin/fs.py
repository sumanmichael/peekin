"""Resolve paths inside one root folder and list directories."""

import mimetypes
import stat
from functools import lru_cache
from pathlib import Path

from pygments.lexers import find_lexer_class_for_filename

for _type, _ext in [
    ("image/webp", ".webp"), ("image/avif", ".avif"), ("video/webm", ".webm"),
    ("video/x-matroska", ".mkv"), ("video/quicktime", ".mov"), ("audio/mp4", ".m4a"),
    ("audio/flac", ".flac"), ("audio/ogg", ".opus"),
]:
    mimetypes.add_type(_type, _ext)


class NotFound(Exception):
    """Missing, hidden, unreadable, or outside the root. Callers answer 404 for all."""


@lru_cache(maxsize=4096)
def _has_code_lexer(probe: str) -> bool:
    cls = find_lexer_class_for_filename(probe)
    return cls is not None and cls.__name__ != "TextLexer"


def kind_of(name: str) -> str:
    mime = mimetypes.guess_type(name)[0] or ""
    if mime == "application/pdf":
        return "pdf"
    if mime.startswith("image/"):
        return "image"
    suffix = Path(name).suffix.lower()
    if suffix in (".md", ".markdown"):
        return "markdown"
    # ponytail: keyed by suffix so big folders stay fast; misses name-only lexers like CMakeLists.txt
    if _has_code_lexer("f" + suffix if suffix else name):
        return "code"
    if mime.startswith(("video/", "audio/")):
        return mime.split("/")[0]
    if mime.startswith("text/"):
        return "text"
    return "other"


def _parts(rel: str) -> list[str]:
    return [p for p in rel.split("/") if p not in ("", ".")]


class Root:
    def __init__(self, path, show_hidden: bool = False):
        self.path = Path(path).resolve(strict=True)
        self.show_hidden = show_hidden

    def _hidden(self, parts) -> bool:
        return not self.show_hidden and any(p.startswith(".") for p in parts)

    def resolve(self, rel: str) -> Path:
        """Map a /-separated path relative to the root to a real path inside it."""
        parts = _parts(rel)
        if "\x00" in rel or rel.startswith("/") or self._hidden(parts):
            raise NotFound(rel)
        try:
            target = self.path.joinpath(*parts).resolve(strict=True)
        except (OSError, RuntimeError):
            raise NotFound(rel) from None
        if not target.is_relative_to(self.path) or self._hidden(target.relative_to(self.path).parts):
            raise NotFound(rel)
        return target

    def listdir(self, rel: str) -> list[dict]:
        folder = self.resolve(rel)
        if not folder.is_dir():
            raise NotADirectoryError(rel)
        try:
            children = list(folder.iterdir())
        except OSError:
            raise NotFound(rel) from None
        prefix = "/".join(_parts(rel))
        entries = []
        for child in children:
            if self._hidden([child.name]):
                continue
            try:
                real = child.resolve(strict=True)
                st = real.stat()
            except (OSError, RuntimeError):
                continue  # broken symlink or unreadable entry
            if not real.is_relative_to(self.path):
                continue
            is_dir = stat.S_ISDIR(st.st_mode)
            entries.append({
                "name": child.name,
                "path": f"{prefix}/{child.name}" if prefix else child.name,
                "type": "dir" if is_dir else "file",
                "kind": "dir" if is_dir else kind_of(child.name),
                "size": 0 if is_dir else st.st_size,
                "mtime": int(st.st_mtime),
            })
        return sorted(entries, key=lambda e: (e["type"] != "dir", e["name"].casefold()))
