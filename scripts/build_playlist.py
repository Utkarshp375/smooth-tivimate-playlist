#!/usr/bin/env python3
"""Combine authorized remote and local M3U playlists.

Remote sources: HTTPS URLs in config/sources.txt (one per line).
Local sources: .m3u/.m3u8 files in sources/.
Output: output/smooth_playlist.m3u
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


def parse_m3u(text: str, source_name: str) -> list[tuple[list[str], str]]:
    """Return channel blocks as (metadata lines, stream URL), preserving tags."""
    entries: list[tuple[list[str], str]] = []
    pending: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF"):
            # A new channel starts; discard any incomplete previous block.
            pending = [line]
        elif line.startswith("#"):
            # Keep per-channel directives such as EXTVLCOPT and KODIPROP.
            if pending:
                pending.append(line)
        else:
            metadata = pending or [f'#EXTINF:-1 group-title="Other",{source_name}']
            entries.append((metadata, line))
            pending = []

    return entries


def load_remote(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        raise ValueError("Only valid HTTPS playlist URLs are accepted")
    response = requests.get(
        url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}
    )
    response.raise_for_status()
    return response.text


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    entries: list[tuple[list[str], str]] = []
    seen_urls: set[str] = set()
    sources_loaded = 0

    if SOURCE_LIST.exists():
        for line_number, raw in enumerate(read_text(SOURCE_LIST).splitlines(), 1):
            url = raw.strip()
            if not url or url.startswith("#"):
                continue
            try:
                source_entries = parse_m3u(load_remote(url), url)
                sources_loaded += 1
                for metadata, stream_url in source_entries:
                    if stream_url not in seen_urls:
                        entries.append((metadata, stream_url))
                        seen_urls.add(stream_url)
                print(f"[OK] Loaded remote source line {line_number}: {len(source_entries)} channels")
            except Exception as exc:
                print(f"[WARN] Remote source line {line_number} failed: {exc}")

    if LOCAL_SOURCES.exists():
        files = sorted(
            list(LOCAL_SOURCES.glob("*.m3u"))
            + list(LOCAL_SOURCES.glob("*.m3u8"))
        )
        for path in files:
            try:
                source_entries = parse_m3u(read_text(path), path.stem)
                sources_loaded += 1
                for metadata, stream_url in source_entries:
                    if stream_url not in seen_urls:
                        entries.append((metadata, stream_url))
                        seen_urls.add(stream_url)
                print(f"[OK] Loaded local file {path.name}: {len(source_entries)} channels")
            except Exception as exc:
                print(f"[WARN] Local file {path.name} failed: {exc}")

    if not entries:
        print("No channels found.")
        print("Add authorized HTTPS M3U URLs to config/sources.txt or files to sources/.")
        return 1

    temp_file = OUTPUT_FILE.with_suffix(".m3u.tmp")
    with temp_file.open("w", encoding="utf-8", newline="\n") as output:
        output.write("#EXTM3U\n")
        for metadata, stream_url in entries:
            for metadata_line in metadata:
                output.write(f"{metadata_line}\n")
            output.write(f"{stream_url}\n")
    temp_file.replace(OUTPUT_FILE)

    print(
        f"Built {len(entries)} unique channels from {sources_loaded} sources: "
        f"{OUTPUT_FILE.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
