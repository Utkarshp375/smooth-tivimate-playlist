#!/usr/bin/env python3
"""Build a combined M3U playlist from authorized source playlists.

Add HTTPS playlist URLs to config/sources.txt (one per line), or place local
.m3u/.m3u8 files in sources/. Output: output/smooth_playlist.m3u.
"""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urlsplit

import requests

ROOT = Path(__file__).resolve().parents[1]
SOURCE_LIST = ROOT / "config" / "sources.txt"
LOCAL_SOURCES = ROOT / "sources"
OUTPUT_DIR = ROOT / "output"
OUTPUT_FILE = OUTPUT_DIR / "smooth_playlist.m3u"
TIMEOUT = 25
USER_AGENT = "Mozilla/5.0 (compatible; SmoothPlaylistBuilder/1.0)"


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def parse_m3u(text: str, source_name: str) -> list[tuple[str, str]]:
    """Parse M3U into (EXTINF metadata, stream URL) pairs."""
    entries: list[tuple[str, str]] = []
    pending_extinf: str | None = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF"):
            pending_extinf = line
        elif line.startswith("#"):
            continue
        else:
            metadata = pending_extinf or f'#EXTINF:-1 group-title="Other",{source_name}'
            entries.append((metadata, line))
            pending_extinf = None
    return entries


def load_remote(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc:
        raise ValueError("Only valid HTTPS playlist URLs are accepted")
    response = requests.get(
        url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}
    )
    response.raise_for_status()
    return response.text


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    entries: list[tuple[str, str]] = []
    seen_urls: set[str] = set()

    if SOURCE_LIST.exists():
        for line_number, raw in enumerate(read_text(SOURCE_LIST).splitlines(), 1):
            url = raw.strip()
            if not url or url.startswith("#"):
                continue
            try:
                for metadata, stream_url in parse_m3u(load_remote(url), url):
                    if stream_url not in seen_urls:
                        entries.append((metadata, stream_url))
                        seen_urls.add(stream_url)
                print(f"[OK] Loaded source on line {line_number}")
            except Exception as exc:
                print(f"[WARN] Source line {line_number}: {exc}")

    if LOCAL_SOURCES.exists():
        files = sorted(
            list(LOCAL_SOURCES.glob("*.m3u"))
            + list(LOCAL_SOURCES.glob("*.m3u8"))
        )
        for path in files:
            try:
                for metadata, stream_url in parse_m3u(read_text(path), path.stem):
                    if stream_url not in seen_urls:
                        entries.append((metadata, stream_url))
                        seen_urls.add(stream_url)
                print(f"[OK] Loaded local file: {path.name}")
            except Exception as exc:
                print(f"[WARN] Local file {path.name}: {exc}")

    if not entries:
        print("No channels found. Add HTTPS playlist URLs to config/sources.txt")
        print("or add .m3u/.m3u8 files to the sources/ folder.")
        return 1

    with OUTPUT_FILE.open("w", encoding="utf-8", newline="\n") as output:
        output.write("#EXTM3U\n")
        for metadata, stream_url in entries:
            output.write(f"{metadata}\n{stream_url}\n")

    print(f"Built {len(entries)} unique channels: {OUTPUT_FILE.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
