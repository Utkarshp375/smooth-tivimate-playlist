#!/usr/bin/env python3
"""Check playlist URL reachability without publishing redirect tokens."""
from __future__ import annotations

import concurrent.futures
import json
import re
import time
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import requests

ROOT = Path(__file__).resolve().parents[1]
PLAYLIST = ROOT / "output" / "smooth_playlist.m3u"
OUTPUT_DIR = ROOT / "output"
REPORT_FILE = OUTPUT_DIR / "checker_report.json"
FAILED_FILE = OUTPUT_DIR / "failed_urls.txt"

MAX_WORKERS = 8
TIMEOUT = 15
USER_AGENT = "Mozilla/5.0 (compatible; SmoothPlaylistLinkChecker/1.1)"
VALID_SCHEMES = {"http", "https"}
SENSITIVE_QUERY_KEYS = {
    "hdnea", "hdntl", "token", "access_token", "auth", "authorization",
    "signature", "sig", "policy", "expires", "expiry", "exp", "jwt",
    "session", "sessionid", "cookie", "key", "x-amz-signature",
    "x-amz-credential", "x-amz-security-token",
}


def sanitize_url(url: str) -> str:
    """Redact credential-like query values before writing public reports."""
    parsed = urlsplit(url)
    safe_query = [
        (key, "[REDACTED]" if key.lower() in SENSITIVE_QUERY_KEYS else value)
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
        # Exception messages can contain signed URLs; publish only the class.
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
            "401/403 can indicate provider restrictions. Sensitive query values "
            "are redacted from this report."
        ),
    }
    REPORT_FILE.write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    failed = [item for item in results if item["status"] != "reachable"]
    FAILED_FILE.write_text(
        "".join(
            f"{item['name']} | {item['url']} | {item['status']}\n"
            for item in failed
        ),
        encoding="utf-8",
    )
    print("\nSummary:")
    for status, count in sorted(counts.items()):
        print(f"  {status}: {count}")
    print(f"Report: {REPORT_FILE.relative_to(ROOT)}")
    print(f"Non-reachable list: {FAILED_FILE.relative_to(ROOT)}")
    print("Failed/restricted links are reported, not automatically removed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
