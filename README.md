# peekin

A lightweight, read-only file browser for your web browser. Browse a folder and
preview images (swipeable gallery), video, audio, PDF, and source code with
syntax highlighting. Works on desktop and phone. Fully offline.

## Run

```bash
uvx peekin                     # share the current folder on http://127.0.0.1:8000
uvx peekin ~/Pictures --open   # share a folder and open the browser
python -m peekin               # after: pip install peekin
```

Until the first PyPI release:

```bash
uvx --from git+https://github.com/sumanmichael/peekin peekin
```

## Share on your network

```bash
uvx peekin --host 0.0.0.0
```

peekin needs a password whenever it listens on something other than
localhost. If you don't set one, it generates one and prints it at startup.
Set your own with `PEEKIN_PASSWORD=...` or `--password-file FILE`.
`--no-password` turns the password off (not recommended on shared networks).

## Options

| Option | Default | Meaning |
|---|---|---|
| `FOLDER` | `.` | Folder to share |
| `--host` | `127.0.0.1` | Address to listen on (`0.0.0.0` for your network) |
| `--port` | `8000` | Port |
| `--password-file` | | Read the password from this file's first line |
| `--no-password` | off | Never ask for a password |
| `--thumbs` | off | Image thumbnails in grid view (install with `uvx --from 'peekin[thumbs]' peekin --thumbs`) |
| `--show-hidden` | off | Show dotfiles |
| `--open` | off | Open the browser |

## Security

- Read-only: nothing in the shared folder can be changed through peekin.
- Paths cannot escape the shared folder, including through symlinks.
- Five wrong passwords lock that IP address out for 60 seconds, doubling each time.
- HTML and SVG files are downloaded, never rendered, so files you share can't run scripts in peekin.
- Other websites you visit can't read your files through peekin: cross-site requests are blocked, and
  without a password peekin only answers to IP addresses, `localhost`, and `*.local` names.
- No HTTPS: use it on networks you trust, not on the public internet.

## Develop

```bash
uv run pytest
uv run peekin .
```

## Release

1. Bump `__version__` in `src/peekin/__init__.py` and commit.
2. `gh release create vX.Y.Z --generate-notes` (the tag must match the version).
3. The `publish` workflow tests, builds, and uploads to PyPI via trusted publishing.

## License

MIT
