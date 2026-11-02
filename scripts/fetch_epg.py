#!/usr/bin/env python3
"""Download an authorized XMLTV EPG feed to output/epg.xml."""
from __future__ import annotations
import os, sys
from pathlib import Path
from urllib.parse import urlsplit
import requests

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "epg.xml"
TIMEOUT = 45
MAX_BYTES = 100 * 1024 * 1024

def main() -> int:
    url = os.getenv("EPG_URL", "").strip()
    if not url:
        print("[INFO] EPG_URL is not configured; skipping EPG download.")
        return 0
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.netloc:
        print("[ERROR] EPG_URL must be a valid HTTPS URL.")
        return 1
    try:
        with requests.get(url, timeout=TIMEOUT, stream=True,
                          headers={"User-Agent": "SmoothPlaylistEPG/1.0"}) as response:
            response.raise_for_status()
            chunks, total = [], 0
            for chunk in response.iter_content(1024 * 256):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError("EPG feed exceeds 100 MB safety limit")
                chunks.append(chunk)
        data = b"".join(chunks)
        if not (data.lstrip().startswith(b"<?xml") or b"<tv" in data[:4096]):
            raise ValueError("Response does not look like XMLTV data")
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        temp = OUTPUT.with_suffix(".xml.tmp")
        temp.write_bytes(data)
        temp.replace(OUTPUT)
        print(f"[OK] Saved EPG feed ({total} bytes)")
        return 0
    except Exception as exc:
        print(f"[ERROR] EPG download failed: {exc}")
        return 1

if __name__ == "__main__":
    sys.exit(main())
