#!/usr/bin/env python3
"""Combine public M3U sources and local playlists into a TiviMate playlist.

The sportlive18 All-Playlist feed is treated as an untrusted upstream source:
entries carrying DRM/license directives, cookies, signed/expiring URLs, or
subscription-service labels are excluded. This builder never creates tokens,
fetches credentials, or bypasses access controls.
"""
from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit

import requests

ROOT = Path(__file__).resolve().parents[1]
SOURCE_LIST = ROOT / "config" / "sources.txt"
LOCAL_SOURCES = ROOT / "sources"
OUTPUT_DIR = ROOT / "output"
OUTPUT_FILE = OUTPUT_DIR / "smooth_playlist.m3u"
TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (compatible; SmoothTiviMatePlaylist/2.0)"

# Subscription/OTT labels are intentionally excluded from third-party feeds.
BLOCKED_LABELS = (
    "fancode", "sonyliv", "sony liv", "jio hotstar", "hotstar",
    "prime video", "primevideo", "willow", "zee5", "vzy",
)
# These are authentication/session parameters, not stable public stream URLs.
BLOCKED_QUERY_KEYS = {
    "hdnea", "hdntl", "token", "access_token", "auth", "authorization",
    "signature", "sig", "policy", "expires", "expiry", "exp", "jwt",
    "session", "sessionid", "cookie", "key",
}
BLOCKED_DIRECTIVE_PREFIXES = (
    "#KODIPROP:",
    "#EXTHTTP:",
)
BLOCKED_DIRECTIVE_CONTAINS = (
    "http-cookie=",
)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def _metadata_label(metadata: list[str]) -> str:
    return " ".join(line for line in metadata if line.startswith("#EXTINF")).lower()


def _is_safe_public_entry(metadata: list[str], stream_url: str) -> tuple[bool, str]:
    """Reject DRM, cookies, OTT-labelled and expiring/authenticated entries."""
    for line in metadata:
        upper = line.upper()
        if upper.startswith(BLOCKED_DIRECTIVE_PREFIXES):
            return False, "DRM/license or custom authorization directive"
        if any(token in line.lower() for token in BLOCKED_DIRECTIVE_CONTAINS):
            return False, "cookie-based stream"
    label = _metadata_label(metadata)
    if any(term in label for term in BLOCKED_LABELS):
        return False, "subscription-service entry"
    try:
        parsed = urlsplit(stream_url)
    except ValueError:
        return False, "invalid URL"
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return False, "non-web stream URL"
    host = parsed.hostname.lower() if parsed.hostname else ""
    if any(term.replace(" ", "") in host.replace("-", "") for term in
           ("hotstar", "sonyliv", "fancode", "primevideo", "willow", "zee5")):
        return False, "subscription-service host"
    query_keys = {key.lower() for key, _ in parse_qsl(parsed.query, keep_blank_values=True)}
    if query_keys & BLOCKED_QUERY_KEYS:
        return False, "signed or expiring URL"
    if re.search(r"(?:hdnea|hdntl|token|signature|policy|expires|jwt)=", parsed.query, re.I):
        return False, "signed or expiring URL"
    return True, ""


def parse_m3u(text: str, source_name: str) -> list[tuple[list[str], str]]:
    """Return safe channel blocks as (metadata lines, stream URL)."""
    entries: list[tuple[list[str], str]] = []
    pending: list[str] = []
    filtered = 0

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF"):
            pending = [line]
        elif line.startswith("#"):
            if pending:
                pending.append(line)
        else:
            metadata = pending or [f'#EXTINF:-1 group-title="Other",{source_name}']
            safe, reason = _is_safe_public_entry(metadata, line)
            if safe:
                entries.append((metadata, line))
            else:
                filtered += 1
                print(f"[FILTER] {source_name}: {reason}")
            pending = []

    if filtered:
        print(f"[INFO] Filtered {filtered} protected/temporary entries from {source_name}")
    return entries


def load_remote(url: str) -> str:
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        raise ValueError("Only valid HTTPS playlist source URLs are accepted")
    response = requests.get(
        url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT}
    )
    response.raise_for_status()
    if len(response.content) > 50 * 1024 * 1024:
        raise ValueError("Playlist source exceeds 50 MB limit")
    return response.text


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    entries: list[tuple[list[str], str]] = []
    seen_urls: set[str] = set()
    sources_loaded = 0
    failed_sources = 0

    if SOURCE_LIST.exists():
        for line_number, raw in enumerate(read_text(SOURCE_LIST).splitlines(), 1):
            url = raw.strip()
            if not url or url.startswith("#"):
                continue
            try:
                source_entries = parse_m3u(load_remote(url), url)
                sources_loaded += 1
                added = 0
                for metadata, stream_url in source_entries:
                    if stream_url not in seen_urls:
                        entries.append((metadata, stream_url))
                        seen_urls.add(stream_url)
                        added += 1
                print(f"[OK] Remote source {line_number}: {added} unique channels")
            except Exception as exc:
                failed_sources += 1
                print(f"[WARN] Remote source {line_number} failed: {exc}")

    if LOCAL_SOURCES.exists():
        files = sorted(
            list(LOCAL_SOURCES.glob("*.m3u"))
            + list(LOCAL_SOURCES.glob("*.m3u8"))
        )
        for path in files:
            try:
                source_entries = parse_m3u(read_text(path), path.stem)
                sources_loaded += 1
                added = 0
                for metadata, stream_url in source_entries:
                    if stream_url not in seen_urls:
                        entries.append((metadata, stream_url))
                        seen_urls.add(stream_url)
                        added += 1
                print(f"[OK] Local source {path.name}: {added} unique channels")
            except Exception as exc:
                failed_sources += 1
                print(f"[WARN] Local source {path.name} failed: {exc}")

    if not entries:
        print("No safe channels found. Check source URLs and playlist availability.")
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
        f"Built {len(entries)} unique safe channels from {sources_loaded} sources "
        f"({failed_sources} source failures): {OUTPUT_FILE.relative_to(ROOT)}"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
