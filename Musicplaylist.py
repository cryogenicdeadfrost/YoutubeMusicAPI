"""Advanced YouTube Music playlist toolkit.

Features:
- OAuth-backed playlist fetch through ytmusicapi
- Fallback public playlist extraction through yt-dlp
- Optional link resolution through youtubesearchpython
- CLI mode for automation
- Local Tkinter GUI for interactive use
"""

from __future__ import annotations

import argparse
import queue
import re
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from youtubesearchpython import VideosSearch
from ytmusicapi import YTMusic
import yt_dlp


@dataclass
class Track:
    title: str
    artists: str = ""
    video_id: str = ""
    source: str = ""

    @property
    def search_query(self) -> str:
        return f"{self.title} {self.artists}".strip()

    @property
    def youtube_url(self) -> str:
        return f"https://www.youtube.com/watch?v={self.video_id}" if self.video_id else ""


class PlaylistToolkit:
    def __init__(self, oauth_path: str = "oauth.json") -> None:
        self.oauth_path = oauth_path

    def _extract_playlist_id(self, playlist: str) -> str:
        if "list=" in playlist:
            match = re.search(r"[?&]list=([^&]+)", playlist)
            if match:
                return match.group(1)
        return playlist.strip()

    def fetch_tracks(self, playlist: str, limit: int = 20) -> list[Track]:
        playlist_id = self._extract_playlist_id(playlist)
        errors: list[str] = []

        # Primary: ytmusicapi (best metadata, requires oauth)
        try:
            ytmusic = YTMusic(self.oauth_path)
            raw = ytmusic.get_playlist(playlist_id, limit=limit)
            tracks = [
                Track(
                    title=item.get("title", "Unknown title"),
                    artists=", ".join(a.get("name", "") for a in item.get("artists", [])),
                    video_id=item.get("videoId", ""),
                    source="ytmusicapi",
                )
                for item in raw.get("tracks", [])
                if item
            ]
            if tracks:
                return tracks
            errors.append("ytmusicapi returned no tracks")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"ytmusicapi failed: {exc}")

        # Fallback: yt-dlp extraction from public playlist url/id
        try:
            playlist_url = (
                playlist
                if playlist.startswith("http")
                else f"https://www.youtube.com/playlist?list={playlist_id}"
            )
            opts = {"quiet": True, "extract_flat": True, "skip_download": True}
            with yt_dlp.YoutubeDL(opts) as ydl:
                info = ydl.extract_info(playlist_url, download=False)

            entries = info.get("entries", []) if isinstance(info, dict) else []
            tracks = []
            for entry in entries[:limit]:
                if not entry:
                    continue
                tracks.append(
                    Track(
                        title=entry.get("title", "Unknown title"),
                        artists=entry.get("uploader", ""),
                        video_id=entry.get("id", ""),
                        source="yt-dlp",
                    )
                )
            if tracks:
                return tracks
            errors.append("yt-dlp returned no entries")
        except Exception as exc:  # noqa: BLE001
            errors.append(f"yt-dlp fallback failed: {exc}")

        raise RuntimeError("Unable to fetch tracks. " + " | ".join(errors))

    def resolve_missing_links(self, tracks: list[Track]) -> list[Track]:
        for track in tracks:
            if track.video_id:
                continue
            try:
                result = VideosSearch(track.search_query, limit=1).result()
                top = result["result"][0]
                link = top.get("link", "")
                match = re.search(r"v=([\w-]+)", link)
                if match:
                    track.video_id = match.group(1)
                    track.source += "+search"
            except Exception:  # noqa: BLE001
                continue
        return tracks

    def download_tracks(
        self,
        tracks: list[Track],
        output_dir: str,
        quality: str = "bestaudio/best",
        dry_run: bool = False,
        logger: Callable[[str], None] | None = None,
    ) -> None:
        logger = logger or (lambda _msg: None)
        Path(output_dir).mkdir(parents=True, exist_ok=True)

        links = [track.youtube_url for track in tracks if track.youtube_url]
        if not links:
            raise RuntimeError("No downloadable links were resolved.")

        ydl_opts = {
            "format": quality,
            "outtmpl": str(Path(output_dir) / "%(playlist_index)s - %(title)s.%(ext)s"),
            "noplaylist": True,
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": "192",
                }
            ],
        }

        if dry_run:
            for idx, track in enumerate(tracks, start=1):
                if track.youtube_url:
                    logger(f"[DRY-RUN] {idx}. {track.title} -> {track.youtube_url}")
            return

        for idx, track in enumerate(tracks, start=1):
            if not track.youtube_url:
                logger(f"[SKIP] {idx}. {track.title} (no video id)")
                continue
            logger(f"[DL] {idx}/{len(tracks)} {track.title}")
            with yt_dlp.YoutubeDL(ydl_opts) as ydl:
                ydl.download([track.youtube_url])


def run_cli(args: argparse.Namespace) -> None:
    toolkit = PlaylistToolkit(oauth_path=args.oauth)
    tracks = toolkit.fetch_tracks(args.playlist, args.limit)
    tracks = toolkit.resolve_missing_links(tracks)

    print("\nResolved tracks:")
    for i, track in enumerate(tracks, start=1):
        print(f"{i:02d}. {track.title} | {track.artists} | {track.source}")

    toolkit.download_tracks(
        tracks,
        output_dir=args.output,
        quality=args.quality,
        dry_run=args.dry_run,
        logger=print,
    )


def run_gui() -> None:
    import tkinter as tk
    from tkinter import filedialog, ttk

    toolkit = PlaylistToolkit()
    log_queue: queue.Queue[str] = queue.Queue()

    root = tk.Tk()
    root.title("YouTube Music API Toolkit")
    root.geometry("900x650")

    playlist_var = tk.StringVar(value="https://www.youtube.com/playlist?list=")
    oauth_var = tk.StringVar(value="oauth.json")
    limit_var = tk.IntVar(value=10)
    output_var = tk.StringVar(value="downloads")
    dry_run_var = tk.BooleanVar(value=True)
    progress_var = tk.DoubleVar(value=0)

    frm = ttk.Frame(root, padding=14)
    frm.pack(fill="both", expand=True)

    ttk.Label(frm, text="Playlist URL / ID").grid(row=0, column=0, sticky="w")
    ttk.Entry(frm, textvariable=playlist_var, width=90).grid(row=1, column=0, columnspan=3, sticky="ew", pady=(0, 8))

    ttk.Label(frm, text="OAuth file").grid(row=2, column=0, sticky="w")
    ttk.Entry(frm, textvariable=oauth_var, width=60).grid(row=3, column=0, sticky="ew", pady=(0, 8))

    def browse_oauth() -> None:
        path = filedialog.askopenfilename(title="Select oauth.json")
        if path:
            oauth_var.set(path)

    ttk.Button(frm, text="Browse", command=browse_oauth).grid(row=3, column=1, sticky="w", padx=6)

    ttk.Label(frm, text="Limit").grid(row=4, column=0, sticky="w")
    ttk.Spinbox(frm, from_=1, to=200, textvariable=limit_var, width=8).grid(row=5, column=0, sticky="w")

    ttk.Label(frm, text="Output folder").grid(row=6, column=0, sticky="w", pady=(8, 0))
    ttk.Entry(frm, textvariable=output_var, width=60).grid(row=7, column=0, sticky="ew", pady=(0, 8))

    def browse_output() -> None:
        path = filedialog.askdirectory(title="Select output folder")
        if path:
            output_var.set(path)

    ttk.Button(frm, text="Select Folder", command=browse_output).grid(row=7, column=1, sticky="w", padx=6)

    ttk.Checkbutton(frm, text="Dry run (resolve only, no download)", variable=dry_run_var).grid(row=8, column=0, sticky="w", pady=(4, 8))

    prog = ttk.Progressbar(frm, variable=progress_var, maximum=100)
    prog.grid(row=9, column=0, columnspan=3, sticky="ew", pady=(4, 10))

    log = tk.Text(frm, wrap="word", height=24)
    log.grid(row=10, column=0, columnspan=3, sticky="nsew")
    frm.rowconfigure(10, weight=1)
    frm.columnconfigure(0, weight=1)

    def add_log(message: str) -> None:
        log.insert("end", message + "\n")
        log.see("end")

    def process_queue() -> None:
        while not log_queue.empty():
            add_log(log_queue.get())
        root.after(200, process_queue)

    def worker() -> None:
        try:
            progress_var.set(10)
            toolkit.oauth_path = oauth_var.get().strip()
            tracks = toolkit.fetch_tracks(playlist_var.get().strip(), int(limit_var.get()))
            log_queue.put(f"Fetched {len(tracks)} tracks")
            progress_var.set(45)
            tracks = toolkit.resolve_missing_links(tracks)
            log_queue.put("Resolved missing links")
            progress_var.set(60)
            toolkit.download_tracks(
                tracks,
                output_dir=output_var.get().strip(),
                dry_run=dry_run_var.get(),
                logger=lambda m: log_queue.put(m),
            )
            progress_var.set(100)
            log_queue.put("Completed successfully ✅")
        except Exception as exc:  # noqa: BLE001
            log_queue.put(f"Error: {exc}")
            progress_var.set(0)

    def start() -> None:
        log.delete("1.0", "end")
        progress_var.set(0)
        threading.Thread(target=worker, daemon=True).start()

    ttk.Button(frm, text="Run Toolkit", command=start).grid(row=11, column=0, sticky="w", pady=(10, 0))

    process_queue()
    root.mainloop()


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="YouTube Music playlist toolkit")
    parser.add_argument("--gui", action="store_true", help="Launch local GUI")
    parser.add_argument("--playlist", default="PLd5ZrsVFhP8oxHt7ExLl55Qj-j46_8uix", help="Playlist URL or ID")
    parser.add_argument("--oauth", default="oauth.json", help="Path to oauth json")
    parser.add_argument("--limit", default=10, type=int, help="Max number of tracks")
    parser.add_argument("--output", default="downloads", help="Output directory")
    parser.add_argument("--quality", default="bestaudio/best", help="yt-dlp format selector")
    parser.add_argument("--dry-run", action="store_true", help="Resolve links only")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.gui:
        run_gui()
    else:
        run_cli(args)


if __name__ == "__main__":
    main()
