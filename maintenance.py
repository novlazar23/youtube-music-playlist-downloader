#!/usr/bin/env python3
import argparse
import shutil
import subprocess
import sys
from pathlib import Path

from mutagen.id3 import ID3, ID3NoHeaderError, TALB, TPE2


def die(msg: str, code: int = 1) -> None:
    print(f"ERROR: {msg}", file=sys.stderr)
    raise SystemExit(code)


def list_mp3s(album_dir: Path) -> list[Path]:
    return sorted([p for p in album_dir.glob("*.mp3") if p.is_file()])


def clean_empty_id3(album_dir: Path) -> None:
    files = list_mp3s(album_dir)
    if not files:
        die(f"No MP3 files found in {album_dir}")

    changed = 0
    for f in files:
        try:
            tags = ID3(str(f))
        except ID3NoHeaderError:
            continue

        to_delete = []
        for key, frame in tags.items():
            if key.startswith("APIC"):
                continue
            text = None
            if hasattr(frame, "text"):
                joined = " ".join([str(x).strip() for x in frame.text if str(x).strip()]).strip()
                text = joined
            if text is not None and text == "":
                to_delete.append(key)

        if to_delete:
            for k in to_delete:
                del tags[k]
            tags.save(v2_version=3)
            changed += 1

    print(f"Cleanup empty tags: {changed} file(s) changed")


def set_album_albumartist_from_folder(album_dir: Path) -> None:
    files = list_mp3s(album_dir)
    if not files:
        die(f"No MP3 files found in {album_dir}")

    album = album_dir.name
    for f in files:
        try:
            tags = ID3(str(f))
        except ID3NoHeaderError:
            tags = ID3()
        tags["TALB"] = TALB(encoding=3, text=[album])
        tags["TPE2"] = TPE2(encoding=3, text=[album])
        tags.save(str(f), v2_version=3)

    print(f"Set Album+Album Artist to '{album}' for {len(files)} file(s)")


def replaygain(album_dir: Path) -> None:
    files = list_mp3s(album_dir)
    if not files:
        die(f"No MP3 files found in {album_dir}")

    rsgain = shutil.which("rsgain")
    mp3gain = shutil.which("mp3gain")

    if rsgain:
        cmd = ["rsgain", "easy"] + [str(f) for f in files]
        print("Running:", " ".join(cmd))
        subprocess.check_call(cmd)
        return

    if mp3gain:
        cmd = ["mp3gain", "-a"] + [str(f) for f in files]
        print("Running:", " ".join(cmd))
        subprocess.check_call(cmd)
        return

    die("Neither 'rsgain' nor 'mp3gain' found in PATH")


def main() -> None:
    p = argparse.ArgumentParser(description="MP3 maintenance: clean empty tags, set Album Artist, ReplayGain")
    p.add_argument("album_dir", help="Album folder, e.g. /downloads/Remixe")
    p.add_argument("--clean-empty", action="store_true")
    p.add_argument("--set-album-artist", action="store_true")
    p.add_argument("--replaygain", action="store_true")

    args = p.parse_args()
    album_dir = Path(args.album_dir).expanduser().resolve()
    if not album_dir.is_dir():
        die(f"Not a directory: {album_dir}")

    did = False
    if args.clean_empty:
        clean_empty_id3(album_dir); did = True
    if args.set_album_artist:
        set_album_albumartist_from_folder(album_dir); did = True
    if args.replaygain:
        replaygain(album_dir); did = True

    if not did:
        die("No action selected. Use --clean-empty and/or --set-album-artist and/or --replaygain", 2)


if __name__ == "__main__":
    main()
