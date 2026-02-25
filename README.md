# YoutubeMusicAPI Toolkit

A fully upgraded local toolkit for fetching YouTube Music playlists, resolving track links, and downloading high-quality local audio.

## What was upgraded

- **Core engine rewritten** into a reusable `PlaylistToolkit` class.
- **Advanced fallback access**:
  - Primary provider: `ytmusicapi` (OAuth, richer metadata).
  - Fallback provider: `yt-dlp` public playlist extraction (works when OAuth/API fails).
  - Final fallback: `youtubesearchpython` link resolution for missing `videoId` values.
- **Dual interface support**:
  - Command-line automation (`--dry-run`, quality/output controls).
  - Local **Tkinter GUI** with logs, progress bar, file pickers, and background worker execution.
- **Safer local UX**:
  - Dry-run mode to validate links before downloading.
  - Better progress + error logging.

## Install

```bash
pip install ytmusicapi yt-dlp youtube-search-python
```

You should also provide a valid `oauth.json` for `ytmusicapi` primary access.

## CLI usage

```bash
python Musicplaylist.py --playlist "https://www.youtube.com/playlist?list=YOUR_LIST_ID" --limit 10 --output downloads
```

Dry run (no download):

```bash
python Musicplaylist.py --playlist "YOUR_LIST_ID" --dry-run
```

Useful flags:

- `--oauth oauth.json`
- `--quality bestaudio/best`
- `--limit 25`
- `--output downloads`

## GUI usage

```bash
python Musicplaylist.py --gui
```

GUI includes:

- Playlist URL/ID input
- OAuth file picker
- Limit + output folder controls
- Dry-run toggle
- Live logs + progress bar

## Project goal

Give you a **complete local spectrum**:

- quick playlist validation,
- resilient track resolution,
- and robust local download behavior,

with both scriptable and visual workflows.
