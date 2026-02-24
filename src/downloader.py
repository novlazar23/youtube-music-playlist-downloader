#!/usr/bin/env python3
import os
import time
import logging
import random
from typing import List, Optional, Dict, Any, Callable, Tuple

import yt_dlp


PlaylistEntry = Tuple[str, str]  # (album_name, url)


class YoutubePlaylistDownloader:
    """Downloads YouTube Music playlists as MP3 files."""

    def __init__(
        self,
        output_dir: str = "./downloads",
        quality: str = "0",
        rate_limit: bool = False,
        max_retries: int = 3,
        retry_sleep: int = 10,
        archive_file: Optional[str] = None,
    ):
        self.output_dir = output_dir
        self.quality = quality
        self.rate_limit = rate_limit
        self.max_retries = max_retries
        self.retry_sleep = retry_sleep
        self.logger = logging.getLogger("ytm-downloader")

        os.makedirs(self.output_dir, exist_ok=True)

        # Download archive (dedupe)
        self.archive_file = archive_file or os.path.join(
            self.output_dir, ".yt-dlp-download-archive.txt"
        )

        self.logger.info(f"Using archive file: {self.archive_file}")

    def _get_ydl_opts(
        self,
        forced_album: str,
        playlist_owner: str = "",
    ) -> dict:
        outtmpl = os.path.join(
            self.output_dir,
            forced_album,
            "%(playlist_index)s - %(title)s.%(ext)s",
        )

        def progress_hook(d: Dict[str, Any]) -> None:
            if d.get("status") == "downloading":
                if "_percent_str" in d and "_eta_str" in d:
                    self.logger.info(
                        f"Downloading: {d.get('filename', '')} - "
                        f"{d.get('_percent_str', '')} (ETA: {d.get('_eta_str', '')})"
                    )
            elif d.get("status") == "finished":
                self.logger.info(
                    f"Downloaded: {d.get('filename', '')} - Converting to MP3..."
                )
            elif d.get("status") == "error":
                self.logger.error(f"Error downloading: {d.get('filename', '')}")

        # Force consistent tags for Navidrome (no genre chips)
        parse_metadata = [
            f"album:{forced_album}",
            "track_number:%(playlist_index)s",
        ]
        if playlist_owner:
            parse_metadata.append(f"album_artist:{playlist_owner}")
        else:
            parse_metadata.append("album_artist:%(playlist_uploader)s")

        return {
            "format": "bestaudio/best",
            "postprocessors": [
                {
                    "key": "FFmpegExtractAudio",
                    "preferredcodec": "mp3",
                    "preferredquality": self.quality,  # "0" best VBR, "320" for CBR 320
                },
                {
                    "key": "FFmpegMetadata",
                    "add_metadata": True,
                },
                {
                    "key": "EmbedThumbnail",
                },
            ],
            "outtmpl": outtmpl,
            "parse_metadata": parse_metadata,
            "ignoreerrors": True,
            "geo_bypass": True,
            "writethumbnail": True,
            "logger": self.logger,
            "progress_hooks": [progress_hook],
            "noprogress": False,

            "socket_timeout": 30,
            "retries": 10,
            "fragment_retries": 10,
            "skip_unavailable_fragments": True,

            "overwrites": False,
            "continuedl": True,

            # Dedupe
            "download_archive": self.archive_file,

            # EJS / JS challenge solving for YouTube
            "js_runtimes": {"deno": {}},
            "remote_components": {"ejs:github"},
        }

    def _with_retry(self, func: Callable, *args, **kwargs) -> Any:
        last_error = None
        for attempt in range(self.max_retries):
            try:
                return func(*args, **kwargs)
            except (yt_dlp.utils.DownloadError, yt_dlp.utils.ExtractorError) as e:
                error_str = str(e).lower()
                if any(
                    err in error_str
                    for err in ["timeout", "connection", "network", "reset", "socket", "ssl"]
                ):
                    self.logger.warning(
                        f"Network error (attempt {attempt+1}/{self.max_retries}): {e}"
                    )
                    last_error = e
                    time.sleep(self.retry_sleep * (attempt + 1))
                else:
                    raise
        raise last_error or Exception("All retry attempts failed")

    def _apply_rate_limit(self) -> None:
        if self.rate_limit:
            delay = random.uniform(1.0, 5.0)
            self.logger.debug(f"Rate limiting: sleeping for {delay:.2f} seconds")
            time.sleep(delay)

    def download_playlist(self, playlist_url: str, forced_album: str) -> None:
        self.logger.info(f"Downloading playlist: {playlist_url} -> album '{forced_album}'")

        # Extract a best-effort playlist owner for Album Artist (optional)
        playlist_owner = ""
        try:
            with yt_dlp.YoutubeDL({"extract_flat": True, "quiet": True}) as ydl:
                info = self._with_retry(ydl.extract_info, playlist_url, download=False)
                playlist_owner = (
                    info.get("uploader") or info.get("channel") or info.get("uploader_id") or ""
                )
        except Exception as e:
            self.logger.warning(f"Could not fetch playlist owner metadata: {e}")

        safe_album = forced_album.replace("/", "_").replace("\\", "_").strip()
        if not safe_album:
            safe_album = "Unknown_Playlist"

        playlist_dir = os.path.join(self.output_dir, safe_album)
        os.makedirs(playlist_dir, exist_ok=True)

        try:
            with yt_dlp.YoutubeDL(self._get_ydl_opts(safe_album, playlist_owner)) as ydl:
                self._with_retry(ydl.download, [playlist_url])

            self.logger.info(f"Download complete → {playlist_dir}")

        except Exception as e:
            self.logger.error(f"Error downloading playlist {playlist_url}: {e}")

        finally:
            self._apply_rate_limit()

    def download_multiple_playlists(self, playlist_entries: List[PlaylistEntry]) -> None:
        total = len(playlist_entries)
        for i, (album_name, url) in enumerate(playlist_entries, 1):
            album_name = (album_name or "").strip()
            url = (url or "").strip()
            if not url:
                continue

            if not album_name:
                # Fallback: derive from metadata if user didn't provide a name
                album_name = "Unknown_Playlist"

            self.logger.info(f"Processing playlist {i}/{total}: {url}")
            try:
                self.download_playlist(url, album_name)
            except Exception as e:
                self.logger.error(f"Failed playlist {url}: {e}")


def setup_logging(verbose: bool = False, log_file: Optional[str] = None) -> None:
    log_level = logging.DEBUG if verbose else logging.INFO
    log_format = "%(asctime)s - %(levelname)s - %(message)s"

    handlers = [logging.StreamHandler()]
    if log_file:
        try:
            os.makedirs(os.path.dirname(log_file), exist_ok=True)
            handlers.append(logging.FileHandler(log_file))
        except PermissionError:
            pass

    logging.basicConfig(level=log_level, format=log_format, handlers=handlers)
