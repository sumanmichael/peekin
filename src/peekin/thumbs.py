"""Optional image thumbnails (needs Pillow), cached outside the shared folder."""

import hashlib
import os
import threading
from pathlib import Path

from PIL import Image, ImageOps

SIZE = 256


class Thumbs:
    # ponytail: cache is never pruned; add an LRU sweep if ~/.cache/peekin grows too large.
    def __init__(self, cache_dir: Path, workers: int = 2):
        self.cache_dir = cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)
        self.slots = threading.Semaphore(workers)

    def get(self, path: Path) -> Path:
        st = path.stat()
        key = hashlib.sha256(f"{path}\0{st.st_mtime_ns}\0{st.st_size}".encode(errors="surrogateescape")).hexdigest()
        out = self.cache_dir / f"{key}.webp"
        if out.exists():
            return out
        with self.slots:
            if out.exists():
                return out
            tmp = out.with_name(f"{key}.{threading.get_ident()}.tmp")
            try:
                with Image.open(path) as im:
                    im = ImageOps.exif_transpose(im)
                    im.thumbnail((SIZE, SIZE))
                    if im.mode not in ("RGB", "RGBA"):
                        im = im.convert("RGBA")
                    im.save(tmp, "WEBP", quality=80)
                os.replace(tmp, out)
            finally:
                tmp.unlink(missing_ok=True)
        return out
