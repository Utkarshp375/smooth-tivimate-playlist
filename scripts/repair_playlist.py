#!/usr/bin/env python3
"""Replace dead playlist links with working alternatives for the same channel.

Only public/authorized M3U sources are considered. Authentication/provider
restrictions (401/403) are deliberately not treated as repairable failures.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from urllib.parse import urlsplit

import requests

try:
    from .build_playlist import (
        LOCAL_SOURCES, OUTPUT_DIR, OUTPUT_FILE, SOURCE_LIST, USER_AGENT,
        _is_safe_public_entry, load_remote, parse_m3u, read_text,
    )
except ImportError:  # Direct execution: python scripts/repair_playlist.py
    from build_playlist import (
        LOCAL_SOURCES, OUTPUT_DIR, OUTPUT_FILE, SOURCE_LIST, USER_AGENT,
        _is_safe_public_entry, load_remote, parse_m3u, read_text,
    )

REPORT_FILE = OUTPUT_DIR / "checker_report.json"
REPAIR_REPORT = OUTPUT_DIR / "repair_report.json"
REPAIR_TIMEOUT = 12
REPAIR_USER_AGENT = USER_AGENT


def entry_name(metadata: list[str]) -> str:
    for line in metadata:
        if line.startswith("#EXTINF"):
            return line.rsplit(",", 1)[-1].strip()
    return "Unknown channel"


def channel_key(metadata: list[str]) -> str:
    """Prefer tvg-id; otherwise require an exact normalized channel name."""
    extinf = next((line for line in metadata if line.startswith("#EXTINF")), "")
    match = re.search(r'\btvg-id=["\']([^"\']+)["\']', extinf, re.I)
    if match and match.group(1).strip():
        return "id:" + re.sub(r"\s+", "", match.group(1).strip().lower())
    name = entry_name(metadata).lower()
    name = re.sub(r"\b(4k|uhd|fhd|hd|sd)\b", " ", name)
    name = re.sub(r"[^a-z0-9]+", "", name)
    return "name:" + name if name else ""


def read_entries(text: str) -> list[tuple[list[str], str]]:
    entries: list[tuple[list[str], str]] = []
    pending: list[str] = []
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
            metadata = pending or ['#EXTINF:-1 group-title="Other",Unknown channel']
            ok, _, clean = _is_safe_public_entry(metadata, line)
            if ok:
                entries.append((clean, line))
            pending = []
    return entries


def repairable(result: dict) -> bool:
    status = result.get("status")
    if status in {"not_found", "error"}:
        return True
    return status == "http_error" and result.get("http_status") in {500, 502, 503, 504}


def candidate_works(url: str) -> bool:
    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        return False
    try:
        with requests.get(
            url,
            headers={"User-Agent": REPAIR_USER_AGENT, "Range": "bytes=0-0"},
            timeout=REPAIR_TIMEOUT,
            allow_redirects=True,
            stream=True,
        ) as response:
            return 200 <= response.status_code < 300
    except requests.RequestException:
        return False


def load_source_entries() -> list[tuple[list[str], str]]:
    all_entries: list[tuple[list[str], str]] = []
    if SOURCE_LIST.exists():
        for raw in read_text(SOURCE_LIST).splitlines():
            url = raw.strip()
            if not url or url.startswith("#"):
                continue
            try:
                all_entries.extend(parse_m3u(load_remote(url), url))
            except Exception as exc:
                print(f"[WARN] Repair source unavailable: {type(exc).__name__}")
    if LOCAL_SOURCES.exists():
        for path in sorted(list(LOCAL_SOURCES.glob("*.m3u")) + list(LOCAL_SOURCES.glob("*.m3u8"))):
            try:
                all_entries.extend(parse_m3u(read_text(path), path.stem))
            except Exception as exc:
                print(f"[WARN] Local repair source unavailable: {path.name}: {type(exc).__name__}")
    return all_entries


def main() -> int:
    if not OUTPUT_FILE.exists() or not REPORT_FILE.exists():
        print("[INFO] Playlist or checker report missing; skipping automatic repair.")
        return 0

    report = json.loads(REPORT_FILE.read_text(encoding="utf-8"))
    failures = {
        (str(item.get("name", "")), str(item.get("url", ""))): item
        for item in report.get("results", [])
        if repairable(item)
    }
    if not failures:
        print("[INFO] No repairable dead links found.")
        REPAIR_REPORT.write_text(json.dumps({"repaired": 0, "items": []}, indent=2), encoding="utf-8")
        return 0

    current = read_entries(read_text(OUTPUT_FILE))
    sources = load_source_entries()
    alternatives: dict[str, list[str]] = {}
    for metadata, url in sources:
        key = channel_key(metadata)
        if key:
            alternatives.setdefault(key, [])
            if url not in alternatives[key]:
                alternatives[key].append(url)

    repaired_items = []
    output: list[tuple[list[str], str]] = []
    tested: set[str] = set()
    for metadata, old_url in current:
        name = entry_name(metadata)
        failure = failures.get((name, old_url))
        if not failure:
            output.append((metadata, old_url))
            continue

        key = channel_key(metadata)
        replacement = None
        for candidate in alternatives.get(key, []):
            if candidate == old_url or candidate in tested:
                continue
            tested.add(candidate)
            if candidate_works(candidate):
                replacement = candidate
                break

        if replacement:
            output.append((metadata, replacement))
            repaired_items.append({"channel": name, "status": "replaced"})
            print(f"[REPAIRED] {name}: working alternative found")
        else:
            output.append((metadata, old_url))
            repaired_items.append({"channel": name, "status": "no_working_alternative"})
            print(f"[UNCHANGED] {name}: no verified alternative")

    temp = OUTPUT_FILE.with_suffix(".m3u.repair.tmp")
    with temp.open("w", encoding="utf-8", newline="\n") as out:
        out.write('#EXTM3U url-tvg="https://raw.githubusercontent.com/Utkarshp375/smooth-tivimate-playlist/main/output/epg.xml"\n')
        for metadata, url in output:
            for line in metadata:
                out.write(line + "\n")
            out.write(url + "\n")
    temp.replace(OUTPUT_FILE)

    REPAIR_REPORT.write_text(
        json.dumps({"repaired": sum(x["status"] == "replaced" for x in repaired_items),
                    "checked": len(repaired_items), "items": repaired_items},
                   ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[INFO] Automatic repair complete: {sum(x['status'] == 'replaced' for x in repaired_items)} link(s) replaced.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
