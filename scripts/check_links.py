#!/usr/bin/env python3
"""Check playlist URL reachability and audit visible token expiry timestamps.

This reports expiry metadata only. It never refreshes cookies or tokens.
"""
from __future__ import annotations

import concurrent.futures
import json
import re
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path
from urllib.parse import parse_qsl, unquote, urlencode, urlsplit, urlunsplit

import requests

ROOT = Path(__file__).resolve().parents[1]
PLAYLIST = ROOT / "output" / "smooth_playlist.m3u"
OUTPUT_DIR = ROOT / "output"
REPORT_FILE = OUTPUT_DIR / "checker_report.json"
FAILED_FILE = OUTPUT_DIR / "failed_urls.txt"
EXPIRY_FILE = OUTPUT_DIR / "expiry_report.json"
RESTRICTED_FILE = OUTPUT_DIR / "restricted_channels.json"

MAX_WORKERS = 8
TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (compatible; SmoothPlaylistLinkChecker/1.2)"
VALID_SCHEMES = {"http", "https"}
IST = timezone(timedelta(hours=5, minutes=30))
SENSITIVE_QUERY_KEYS = {
    "hdnea", "hdntl", "hdnts", "token", "access_token", "auth", "authorization",
    "signature", "sig", "policy", "expires", "expiry", "exp", "jwt",
    "session", "sessionid", "cookie", "key", "x-amz-signature",
    "x-amz-credential", "x-amz-security-token",
}


def sanitize_url(url: str) -> str:
    """Redact credential-like query values before writing public reports."""
    parsed = urlsplit(url)
    safe_query = [
        (key, "[REDACTED]" if re.sub(r"[^a-z0-9]", "", key.lower()) in
         {re.sub(r"[^a-z0-9]", "", x) for x in SENSITIVE_QUERY_KEYS} else value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
    ]
    safe_netloc = parsed.netloc
    if parsed.username is not None or parsed.password is not None:
        host = parsed.hostname or ""
        if ":" in host and not host.startswith("["):
            host = f"[{host}]"
        if parsed.port:
            host = f"{host}:{parsed.port}"
        safe_netloc = host
    return urlunsplit(parsed._replace(netloc=safe_netloc, query=urlencode(safe_query)))


def extract_expiry(url: str, now: float | None = None) -> dict[str, object]:
    """Read an exp=Unix timestamp from a URL or an embedded signed-cookie value."""
    parsed = urlsplit(url)
    candidates = [unquote(url)]
    candidates.extend(unquote(value) for _, value in parse_qsl(parsed.query, keep_blank_values=True))
    timestamps = []
    for candidate in candidates:
        match = re.search(r"(?:^|[~&?;])exp(?:iry)?=(\d{10})(?:\b|$)", candidate, re.I)
        if match:
            timestamps.append(int(match.group(1)))
    if not timestamps:
        return {"expiry_status": "unknown", "expiry_unix": None,
                "expiry_utc": None, "expiry_ist": None, "seconds_remaining": None}
    expiry = min(timestamps)
    current = time.time() if now is None else now
    remaining = int(expiry - current)
    if remaining <= 0:
        status = "expired"
    elif remaining <= 24 * 60 * 60:
        status = "expiring_within_24h"
    else:
        status = "valid_at_check_time"
    dt = datetime.fromtimestamp(expiry, tz=timezone.utc)
    return {
        "expiry_status": status,
        "expiry_unix": expiry,
        "expiry_utc": dt.isoformat(),
        "expiry_ist": dt.astimezone(IST).isoformat(),
        "seconds_remaining": remaining,
    }


def read_playlist(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        raise FileNotFoundError(
            f"Playlist not found: {path}. Run scripts/build_playlist.py first."
        )

    channels: list[dict[str, str]] = []
    pending_name = "Unknown channel"
    for raw in path.read_text(encoding="utf-8-sig", errors="replace").splitlines():
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#EXTINF"):
            pending_name = line.rsplit(",", 1)[-1].strip() or "Unknown channel"
        elif line.startswith("#"):
            continue
        else:
            channels.append({"name": pending_name, "url": line})
            pending_name = "Unknown channel"
    return channels


def check_url(channel: dict[str, str]) -> dict[str, object]:
    url = channel["url"]
    result: dict[str, object] = {
        "name": channel["name"],
        "url": sanitize_url(url),
        "status": "error",
        "http_status": None,
        "final_url": None,
        "response_ms": None,
        "error": None,
        **extract_expiry(url),
    }

    parsed = urlsplit(url)
    if parsed.scheme.lower() not in VALID_SCHEMES or not parsed.netloc:
        result["error"] = "Invalid or unsupported URL (only HTTP/HTTPS allowed)"
        return result

    started = time.monotonic()
    try:
        with requests.get(
            url,
            headers={"User-Agent": USER_AGENT, "Range": "bytes=0-0"},
            timeout=TIMEOUT,
            allow_redirects=True,
            stream=True,
        ) as response:
            result["http_status"] = response.status_code
            result["final_url"] = sanitize_url(response.url)
            result["response_ms"] = round((time.monotonic() - started) * 1000)

            if 200 <= response.status_code < 300:
                result["status"] = "reachable"
            elif response.status_code in (401, 403):
                result["status"] = "restricted"
                result["error"] = "Authentication, token, region, or provider restriction"
            elif response.status_code in (404, 410):
                result["status"] = "not_found"
                result["error"] = "URL not found or expired"
            else:
                result["status"] = "http_error"
                result["error"] = f"HTTP {response.status_code}"
    except requests.RequestException as exc:
        result["response_ms"] = round((time.monotonic() - started) * 1000)
        result["error"] = type(exc).__name__
    return result


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    try:
        channels = read_playlist(PLAYLIST)
    except (OSError, ValueError) as exc:
        print(f"[ERROR] {exc}")
        return 1

    if not channels:
        print("[ERROR] Playlist contains no channel URLs.")
        return 1

    print(f"Checking {len(channels)} URLs with {MAX_WORKERS} workers...")
    with concurrent.futures.ThreadPoolExecutor(max_workers=MAX_WORKERS) as pool:
        results = list(pool.map(check_url, channels))

    counts: dict[str, int] = {}
    for item in results:
        status = str(item["status"])
        counts[status] = counts.get(status, 0) + 1
        print(f"[{status.upper()}] {item['name']} - {item['http_status'] or item['error']}")

    report = {
        "playlist": str(PLAYLIST.relative_to(ROOT)),
        "total": len(results),
        "summary": counts,
        "results": results,
        "note": (
            "Reachability check only. A reachable URL may still fail playback; "
            "401/403 can indicate provider restrictions. Expiry timestamps are "
            "read-only estimates from visible exp parameters; tokens are not renewed. "
            "Sensitive query values are redacted from this report."
        ),
    }
    REPORT_FILE.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    failed = [item for item in results if item["status"] != "reachable"]
    FAILED_FILE.write_text(
        "".join(f"{item['name']} | {item['url']} | {item['status']}\n" for item in failed),
        encoding="utf-8",
    )
    expiry_items = [
        {key: item[key] for key in (
            "name", "expiry_status", "expiry_unix", "expiry_utc",
            "expiry_ist", "seconds_remaining"
        )}
        for item in results if item["expiry_unix"] is not None
    ]
    EXPIRY_FILE.write_text(json.dumps({
        "channels_with_expiry": len(expiry_items),
        "items": expiry_items,
        "note": "Expiry is parsed from the URL only. No cookie/token is refreshed or stored.",
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    restricted = [
        {"name": item["name"], "status": item["status"],
         "http_status": item["http_status"], "url": item["url"]}
        for item in results if item["status"] == "restricted"
    ]
    RESTRICTED_FILE.write_text(json.dumps({
        "restricted_count": len(restricted), "items": restricted,
        "note": "401/403 are reported only; authentication or provider restrictions are not bypassed.",
    }, ensure_ascii=False, indent=2), encoding="utf-8")

    print("\nSummary:")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")
    print(f"Expiry audit: {EXPIRY_FILE.relative_to(ROOT)}")
    print(f"Restricted channels: {RESTRICTED_FILE.relative_to(ROOT)}")
    print(f"Report: {REPORT_FILE.relative_to(ROOT)}")
    print(f"Non-reachable list: {FAILED_FILE.relative_to(ROOT)}")
    print("Expired/restricted access is reported, not renewed or bypassed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
