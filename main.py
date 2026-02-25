#!/usr/bin/env python3
import os
import sys
import time
import argparse
from typing import List, Tuple

from src.downloader import YoutubePlaylistDownloader, setup_logging

# (album, album_artist, url)
PlaylistEntry = Tuple[str, str, str]


def parse_playlists_file(path: str) -> List[PlaylistEntry]:
    """
    playlists.txt supported formats:
      1) Album|Artist|URL
      2) Album|URL
      3) URL

    Lines starting with # are ignored.
    """
    entries: List[PlaylistEntry] = []
    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#"):
                continue

            parts = [p.strip() for p in line.split("|")]
            if len(parts) >= 3:
                album = parts[0]
                artist = parts[1]
                url = "|".join(parts[2:]).strip()
                if url:
                    entries.append((album, artist, url))
            elif len(parts) == 2:
                album = parts[0]
                url = parts[1]
                if url:
                    entries.append((album, "", url))
            else:
                url = parts[0]
                if url:
                    entries.append(("", "", url))

    return entries


def run_watchdog(downloader: YoutubePlaylistDownloader, playlists_file: str, interval: int) -> None:
    downloader.logger.info(f"Watchdog active: interval={interval}s file={playlists_file}")
    while True:
        try:
            entries = parse_playlists_file(playlists_file)
            if entries:
                downloader.download_multiple_playlists(entries)
            else:
                downloader.logger.warning("No playlist entries found.")
        except Exception as e:
            downloader.logger.error(f"Watchdog loop error: {e}")
        time.sleep(interval)


def main() -> None:
    parser = argparse.ArgumentParser(description="Download YouTube Music playlists as MP3")
    parser.add_argument("-f", "--file", help="Text file with playlist entries (Album|Artist|URL per line)")
    parser.add_argument("--watch", action="store_true", help="Enable watchdog mode")
    parser.add_argument("--interval", type=int, default=int(os.environ.get("WATCHDOG_INTERVAL", "600")),
                        help="Watchdog interval seconds (default: 600)")

    parser.add_argument("-o", "--output-dir", default=os.environ.get("OUTPUT_DIR", "/downloads"))
    parser.add_argument("-q", "--quality", default=os.environ.get("MP3_QUALITY", "0"),
                        help='MP3 quality: "0" best VBR, "320" for CBR 320')
    parser.add_argument("-r", "--rate-limit", action="store_true",
                        default=os.environ.get("RATE_LIMIT", "0") == "1")
    parser.add_argument("--retries", type=int, default=int(os.environ.get("MAX_RETRIES", "3")))
    parser.add_argument("--archive-file", default=os.environ.get("ARCHIVE_FILE", ""),
                        help="Persistent yt-dlp download archive file")
    parser.add_argument("--log-file", default=os.environ.get("LOG_FILE", ""))
    parser.add_argument("-v", "--verbose", action="store_true",
                        default=os.environ.get("VERBOSE", "0") == "1")

    args = parser.parse_args()
    setup_logging(args.verbose, args.log_file if args.log_file else None)

    if not args.file:
        print("Missing -f/--file (playlists.txt).", file=sys.stderr)
        raise SystemExit(2)

    downloader = YoutubePlaylistDownloader(
        output_dir=args.output_dir,
        quality=args.quality,
        rate_limit=args.rate_limit,
        max_retries=args.retries,
        archive_file=args.archive_file if args.archive_file else None,
    )

    if args.watch:
        run_watchdog(downloader, args.file, args.interval)
        return

    entries = parse_playlists_file(args.file)
    if not entries:
        print("No playlist entries found.", file=sys.stderr)
        raise SystemExit(2)

    downloader.download_multiple_playlists(entries)


if __name__ == "__main__":
    main()
