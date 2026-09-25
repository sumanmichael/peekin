"""Syntax-highlighted previews for code and text files."""

import html
from pathlib import Path

from pygments import highlight
from pygments.formatters import HtmlFormatter
from pygments.lexers import TextLexer, get_lexer_for_filename
from pygments.util import ClassNotFound

MAX_BYTES = 1_000_000
HIGHLIGHT_BYTES = 200_000  # highlighted HTML is ~15x the source; bigger files stay plain
SNIFF_BYTES = 8192


def code_preview(path: Path) -> dict:
    with path.open("rb") as f:
        data = f.read(MAX_BYTES + 1)
    if b"\x00" in data[:SNIFF_BYTES]:
        return {"binary": True, "truncated": False, "html": ""}
    text = data[:MAX_BYTES].decode("utf-8", errors="replace")
    if len(data) > HIGHLIGHT_BYTES:
        return {"binary": False, "truncated": len(data) > MAX_BYTES, "html": f'<pre class="plain">{html.escape(text)}</pre>'}
    try:
        lexer = get_lexer_for_filename(path.name, stripnl=False)
    except ClassNotFound:
        lexer = TextLexer(stripnl=False)
    formatter = HtmlFormatter(linenos="table", cssclass="hl", wrapcode=True)
    return {"binary": False, "truncated": False, "html": highlight(text, lexer, formatter)}
