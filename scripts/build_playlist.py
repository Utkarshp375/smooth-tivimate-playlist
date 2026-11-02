#!/usr/bin/env python3
"""Build a TiviMate playlist from public/authorized M3U sources."""
from __future__ import annotations
import re, sys
from pathlib import Path
from urllib.parse import parse_qsl, urlsplit
import requests

ROOT = Path(__file__).resolve().parents[1]
SOURCE_LIST = ROOT / "config" / "sources.txt"
LOCAL_SOURCES = ROOT / "sources"
OUTPUT_DIR = ROOT / "output"
OUTPUT_FILE = OUTPUT_DIR / "smooth_playlist.m3u"
TIMEOUT = 30
USER_AGENT = "Mozilla/5.0 (compatible; SmoothTiviMatePlaylist/2.1)"
BLOCKED_LABELS = ("fancode", "sonyliv", "sony liv", "jio hotstar", "hotstar",
                  "prime video", "primevideo", "willow", "zee5", "vzy")
BLOCKED_QUERY_KEYS = {"hdnea", "hdntl", "token", "access_token", "auth",
 "authorization", "signature", "sig", "policy", "expires", "expiry", "exp",
 "jwt", "session", "sessionid", "cookie", "key"}
ALLOWED_KODIPROP = {"inputstream", "inputstream.adaptive.manifest_type"}
ALLOWED_VLC_OPTIONS = {"http-user-agent", "http-referrer"}

def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")

def _metadata_label(metadata: list[str]) -> str:
    return " ".join(x for x in metadata if x.startswith("#EXTINF")).lower()

def _safe_metadata(metadata: list[str]) -> tuple[bool, list[str], str]:
    kept = []
    for line in metadata:
        upper, lower = line.upper(), line.lower()
        if upper.startswith("#EXTHTTP:") or any(x in lower for x in
            ("http-cookie=", "license_key=", "license_url=")):
            return False, [], "cookie, custom headers, or DRM/license metadata"
        if upper.startswith("#KODIPROP:"):
            key = line.split("=",  1)[0].split(":", 1)[-1].strip().lower()
            if key not in ALLOWED_KODIPROP:
                return False, [], "DRM or unsupported KODIPROP directive"
            kept.append(line)
        elif upper.startswith("#EXTVLCOPT:"):
            option = line.split("=", 1)[0].split(":", 1)[-1].strip().lower()
            if option in ALLOWED_VLC_OPTIONS:
                kept.append(line)
        elif line.startswith("#EXTINF") or line.startswith("#EXTGRP"):
            kept.append(line)
    return True, kept, ""

def _is_safe_public_entry(metadata: list[str], stream_url: str):
    safe, clean, reason = _safe_metadata(metadata)
    if not safe:
        return False, reason, []
    label = _metadata_label(metadata)
    if any(term in label for term in BLOCKED_LABELS):
        return False, "subscription-service entry", []
    try:
        parsed = urlsplit(stream_url)
    except ValueError:
        return False, "invalid URL", []
    if parsed.scheme.lower() not in {"http", "https"} or not parsed.netloc:
        return False, "non-web stream URL", []
    host = (parsed.hostname or "").lower().replace("-", "")
    if any(term.replace(" ", "") in host for term in
           ("hotstar", "sonyliv", "fancode", "primevideo", "willow", "zee5")):
        return False, "subscription-service host", []
    query_keys = {k.lower() for k, _ in parse_qsl(parsed.query, keep_blank_values=True)}
    if query_keys & BLOCKED_QUERY_KEYS or re.search(
        r"(?:hdnea|hdntl|token|signature|policy|expires|jwt)=", parsed.query, re.I
    ):
        return False, "signed or expiring URL", []
    if parsed.path.lower().endswith(".mpd"):
        existing = {x.split("=", 1)[0].lower() for x in clean
                    if x.upper().startswith("#KODIPROP:")}
        for hint in ("#KODIPROP:inputstream=inputstream.adaptive",
                     "#KODIPROP:inputstream.adaptive.manifest_type=mpd"):
            if hint.split("=", 1)[0].lower() not in existing:
                clean.append(hint)
    return True, "", clean

def parse_m3u(text: str, source_name: str):
    entries, pending, filtered = [], [], 0
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#EXTM3U"):
            continue
        if line.startswith("#EXTINF"):
            pending = [line]
        elif line.startswith("#"):
            if pending:
                pending.append(line)
        else:
            metadata = pending or [f'#EXTINF:-1 group-title="Other",{source_name}']
            ok, reason, clean = _is_safe_public_entry(metadata, line)
            if ok:
                entries.append((clean, line))
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
    response = requests.get(url, timeout=TIMEOUT, headers={"User-Agent": USER_AGENT})
    response.raise_for_status()
    if len(response.content) > 50 * 1024 * 1024:
        raise ValueError("Playlist source exceeds 50 MB limit")
    return response.text

def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    entries, seen, loaded, failures = [], set(), 0, 0
    if SOURCE_LIST.exists():
        for number, raw in enumerate(read_text(SOURCE_LIST).splitlines(), 1):
            url = raw.strip()
            if not url or url.startswith("#"):
                continue
            try:
                batch = parse_m3u(load_remote(url), url)
                loaded += 1
                added = 0
                for metadata, stream in batch:
                    if stream not in seen:
                        entries.append((metadata, stream)); seen.add(stream); added += 1
                print(f"[OK] Remote source {number}: {added} unique channels")
            except Exception as exc:
                failures += 1
                print(f"[WARN] Remote source {number} failed: {exc}")
    if LOCAL_SOURCES.exists():
        files = sorted(list(LOCAL_SOURCES.glob("*.m3u")) +
                       list(LOCAL_SOURCES.glob("*.m3u8")))
        for path in files:
            try:
                batch = parse_m3u(read_text(path), path.stem); loaded += 1
                added = 0
                for metadata, stream in batch:
                    if stream not in seen:
                        entries.append((metadata, stream)); seen.add(stream); added += 1
                print(f"[OK] Local source {path.name}: {added} unique channels")
            except Exception as exc:
                failures += 1
                print(f"[WARN] Local source {path.name} failed: {exc}")
    if not entries:
        print("No safe channels found. Check source URLs and playlist availability.")
        return 1
    temp = OUTPUT_FILE.with_suffix(".m3u.tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as out:
        out.write('#EXTM3U url-tvg="https://raw.githubusercontent.com/Utkarshp375/smooth-tivimate-playlist/main/output/epg.xml"\n')
        for metadata, stream in entries:
            for item in metadata:
                out.write(item + "\n")
            out.write(stream + "\n")
    temp.replace(OUTPUT_FILE)
    print(f"Built {len(entries)} unique safe channels from {loaded} sources "
          f"({failures} source failures): {OUTPUT_FILE.relative_to(ROOT)}")
    return 0

if __name__ == "__main__":
    sys.exit(main())
