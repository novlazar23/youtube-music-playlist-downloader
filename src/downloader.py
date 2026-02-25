#!/usr/bin/env python3
import os
import time
import logging
import random
from typing import List, Optional, Dict, Any, Callable, Tuple

import yt_dlp

# (album, album_artist, url)
PlaylistEntry = Tuple[str, str, str]


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

        self.archive_file = archive_file or os.path.join(
            self.output_dir, ".yt-dlp-download-archive.txt"
        )
        self.logger.info(f"Using archive file: {self.archive_file}")

    def _get_ydl_opts(self, album: str, album_artist: str) -> dict:
        safe_album = (album or "").replace("/", "_").replace("\\", "_").strip() or "Unknown_Playlist"
        safe_album_artist = (album_artist or "").strip()

        outtmpl = os.path.join(
            self.output_dir,
            safe_album,
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
                self.logger.info(f"Downloaded: {d.get('filename', '')} - Converting to MP3...")
            elif d.get("status") == "error":
                self.logger.error(f"Error downloading: {d.get('filename', '')}")

        # Hard-enforce tags on final MP3 (Navidrome-friendly)
        ffmpeg_out_metadata = [
            "-metadata", f"album={safe_album}",
        ]
        if safe_album_artist:
            ffmpeg_out_metadata += ["-metadata", f"album_artist={safe_album_artist}"]
        ffmpeg_out_metadata += ["-metadata", "track=%(playlist_index)s"]

        return {
            "format": "bestaudio/best",
            "postprocessors": [
                {"key": "FFmpegExtractAudio", "preferredcodec": "mp3", "preferredquality": self.quality},
                {"key": "FFmpegMetadata", "add_metadata": True},
                {"key": "EmbedThumbnail"},
            ],
            # Critical: args routed to ExtractAudio ffmpeg OUTPUT position (case-sensitive key)
            "postprocessor_args": {
                "ExtractAudio+ffmpeg_o": ffmpeg_out_metadata
            },
            "outtmpl": outtmpl,
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
            "download_archive": self.archive_file,
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
                if any(err in error_str for err in ["timeout", "connection", "network", "reset", "socket", "ssl"]):
                    self.logger.warning(f"Network error (attempt {attempt+1}/{self.max_retries}): {e}")
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

    def _extract_defaults(self, url: str) -> Tuple[str, str]:
        """Fallback to yt-dlp extraction when album/artist not provided."""
        try:
            with yt_dlp.YoutubeDL({"extract_flat": True, "quiet": True}) as ydl:
                info = self._with_retry(ydl.extract_info, url, download=False)

            title = (info.get("title") or "Unknown_Playlist").strip()
            title = title.replace("/", "_").replace("\\", "_")

            artist = (info.get("uploader") or info.get("channel") or info.get("uploader_id") or "").strip()
            return title, artist
        except Exception as e:
            self.logger.warning(f"Fallback metadata extraction failed for {url}: {e}")
            return "Unknown_Playlist", ""

    def download_playlist(self, url: str, album: str, album_artist: str) -> None:
        # If album/artist not provided, fallback to yt-dlp extraction
        if not album:
            album, extracted_artist = self._extract_defaults(url)
            if not album_artist:
                album_artist = extracted_artist

        safe_album = (album or "Unknown_Playlist").replace("/", "_").replace("\\", "_").strip() or "Unknown_Playlist"
        playlist_dir = os.path.join(self.output_dir, safe_album)
        os.makedirs(playlist_dir, exist_ok=True)

        self.logger.info(f"Downloading: {url} -> Album='{safe_album}' AlbumArtist='{album_artist or ''}'")

        try:
            with yt_dlp.YoutubeDL(self._get_ydl_opts(safe_album, album_artist)) as ydl:
                self._with_retry(ydl.download, [url])
            self.logger.info(f"Download complete → {playlist_dir}")
        except Exception as e:
            self.logger.error(f"Error downloading {url}: {e}")
        finally:
            self._apply_rate_limit()

    def download_multiple_playlists(self, playlist_entries: List[PlaylistEntry]) -> None:
        total = len(playlist_entries)
        for i, (album, album_artist, url) in enumerate(playlist_entries, 1):
            album = (album or "").strip()
            album_artist = (album_artist or "").strip()
            url = (url or "").strip()
            if not url:
                continue
            self.logger.info(f"Processing {i}/{total}: {album or '[auto]'}|{album_artist or '[auto]'}|{url}")
            self.download_playlist(url, album, album_artist)


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
