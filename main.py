#!/usr/bin/env python3
import os
import sys
import time
import argparse
import logging
from typing import List, Optional, Tuple

from src.downloader import YoutubePlaylistDownloader, setup_logging


PlaylistEntry = Tuple[str, str]  # (album_name, url)


def _parse_playlists_file(path: str) -> List[PlaylistEntry]:
    """
    playlists.txt lines:
      Albumname|https://...
    Also accepts plain URLs (then album name will be derived from playlist metadata).
    """
    entries: List[PlaylistEntry] = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            if "|" in line:
                album, url = line.split("|", 1)
                album = album.strip()
                url = url.strip()
                if url:
                    entries.append((album, url))
            else:
                entries.append(("", line))
    return entries


def watchdog(
    downloader: YoutubePlaylistDownloader,
    playlists_file: str,
    interval: int,
) -> None:
    downloader.logger.info(f"Watchdog active (interval={interval}s, file={playlists_file})")
    while True:
        try:
            entries = _parse_playlists_file(playlists_file)
            if entries:
                downloader.download_multiple_playlists(entries)
            else:
                downloader.logger.warning("No playlist entries found.")
        except Exception as e:
            downloader.logger.error(f"Watchdog loop error: {e}")

        time.sleep(interval)


def main():
    parser = argparse.ArgumentParser(description="Download YouTube Music playlists as MP3")

    parser.add_argument(
        "-f",
        "--file",
        default=os.environ.get("PLAYLIST_FILE", ""),
        help="Text file with playlist entries (Album|URL per line)",
    )
    parser.add_argument(
        "--watch",
        action="store_true",
        default=os.environ.get("WATCHDOG", "0") == "1",
        help="Enable watchdog mode",
    )
    parser.add_argument(
        "--interval",
        type=int,
        default=int(os.environ.get("WATCHDOG_INTERVAL", "600")),
        help="Watchdog interval in seconds (default: 600)",
    )

    parser.add_argument(
        "-o",
        "--output-dir",
        default=os.environ.get("OUTPUT_DIR", "/downloads"),
        help="Directory to save downloaded files",
    )
    parser.add_argument(
        "-q",
        "--quality",
        default=os.environ.get("MP3_QUALITY", "0"),
        help='MP3 audio quality: "0" = best VBR, "320" = CBR 320',
    )
    parser.add_argument(
        "-r",
        "--rate-limit",
        action="store_true",
        default=os.environ.get("RATE_LIMIT", "0") == "1",
        help="Enable rate limiting",
    )
    parser.add_argument(
        "--retries",
        type=int,
        default=int(os.environ.get("MAX_RETRIES", "3")),
        help="Number of retries",
    )
    parser.add_argument(
        "--log-file",
        default=os.environ.get("LOG_FILE", ""),
        help="Optional log file path",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        default=os.environ.get("VERBOSE", "0") == "1",
        help="Enable verbose logging",
    )

    parser.add_argument(
        "--archive-file",
        default=os.environ.get("ARCHIVE_FILE", ""),
        help="yt-dlp download archive file (dedupe). Put this on a persistent volume.",
    )

    args = parser.parse_args()
    setup_logging(args.verbose, args.log_file if args.log_file else None)

    downloader = YoutubePlaylistDownloader(
        output_dir=args.output_dir,
        quality=args.quality,
        rate_limit=args.rate_limit,
        max_retries=args.retries,
        archive_file=args.archive_file if args.archive_file else None,
    )

    if not args.file:
        raise SystemExit("Missing -f/--file (playlists.txt).")

    if args.watch:
        watchdog(downloader, args.file, args.interval)
        return

    entries = _parse_playlists_file(args.file)
    if not entries:
        raise SystemExit("No playlist entries found in file.")

    downloader.download_multiple_playlists(entries)


if __name__ == "__main__":
    main()
