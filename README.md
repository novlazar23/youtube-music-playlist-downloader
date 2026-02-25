# YouTube Music Playlist Downloader

A Docker-based tool to download playlists from YouTube Music and convert them to MP3 format. Optimized for stable library organization in Navidrome.

## Features

- Download playlists (including YouTube Music links; redirects to YouTube playlist)
- Convert audio to MP3 via FFmpeg
- Consistent Navidrome tags (hard-enforced on the final MP3):
  - Album = playlist name (from `playlists.txt` if provided)
  - Album Artist = playlist/artist name (from `playlists.txt` if provided)
  - Track number = playlist index (if available)
- Embed cover artwork (thumbnail)
- Skip duplicates across runs using a persistent download archive file
- Watchdog mode: periodically re-check playlists and download new items
- JS challenge support for YouTube via Deno + EJS remote components
- Logging to console and optional file

## Prerequisites

- Docker + Docker Compose

## playlists.txt format (important)

One entry per line. Supported formats:

1) `Album|Artist|URL` (preferred)
2) `Album|URL`
3) `URL` (fallback: album/title + uploader via yt-dlp extraction)

Examples:

```text
Remixe|Mix|https://music.youtube.com/playlist?list=PLxxxxxxxxxxxxxxxx
Hardstyle|DJ Set|https://music.youtube.com/watch?v=xxxxxxxxxxx&list=RDxxxxxxxxxxxx
# fallback example (auto title/uploader):
https://music.youtube.com/playlist?list=PLyyyyyyyyyyyyyyyy
```

## Quick Start (Docker Compose)

```bash
mkdir -p downloads logs
touch playlists.txt download-archive.txt
docker compose up -d --build
```

Downloads go to `./downloads`, logs to `./logs`. The dedupe archive is `./download-archive.txt`.

## Watchdog mode

Runs periodically (default 600s):

```bash
docker compose up -d
```

## Dedupe archive (persistent)

The archive file is appended after a successful download + conversion. Ensure it is mounted/persisted:

```yaml
- ./download-archive.txt:/downloads/download-archive.txt
```

## Maintenance helper

Includes `/app/maintenance.py`:
- `--set-album-artist` : set Album and Album Artist to folder name
- `--clean-empty` : remove empty ID3 frames
- `--replaygain` : compute ReplayGain (uses `mp3gain` inside the container)

Examples:

```bash
docker exec -it ytm-downloader python /app/maintenance.py /downloads/Remixe --set-album-artist
docker exec -it ytm-downloader python /app/maintenance.py /downloads/Remixe --clean-empty
docker exec -it ytm-downloader python /app/maintenance.py /downloads/Remixe --replaygain
```

## License

MIT
