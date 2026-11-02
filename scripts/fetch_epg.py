#!/usr/bin/env python3
"""Download an authorized XMLTV feed (plain XML or .gz) to output/epg.xml."""
from __future__ import annotations

import gzip
import io
import os
import sys
import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import urlsplit

import requests

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "output" / "epg.xml"
TIMEOUT = 45
MAX_BYTES = 100 * 1024 * 1024


def decode_xmltv_payload(data: bytes, max_bytes: int = MAX_BYTES) -> str:
    """Decode XMLTV, safely handling gzip and limiting decompressed size."""
    if data.startswith(b"\x1f\x8b"):
        with gzip.GzipFile(fileobj=io.BytesIO(data)) as stream:
            payload = stream.read(max_bytes + 1)
    else:
        payload = data

    if len(payload) > max_bytes:
        raise ValueError(f"EPG feed exceeds {max_bytes} byte safety limit")

    text = payload.decode("utf-8-sig")
    root = ET.fromstring(text)
    if root.tag.split("}")[-1].lower() != "tv":
        raise ValueError("XML root element must be <tv> (XMLTV)")
    return text


def main() -> int:
    url = os.getenv("EPG_URL", "https://iptv-epg.org/files/epg-in.xml.gz").strip()
    if not url:
        print("[INFO] EPG_URL is not configured; skipping EPG download.")
        return 0

    parsed = urlsplit(url)
    if parsed.scheme.lower() != "https" or not parsed.netloc:
        print("[ERROR] EPG_URL must be a valid HTTPS URL.")
        return 1

    try:
        with requests.get(
            url,
            timeout=TIMEOUT,
            stream=True,
            headers={"User-Agent": "SmoothPlaylistEPG/1.1"},
        ) as response:
            response.raise_for_status()
            chunks = []
            total = 0
            for chunk in response.iter_content(256 * 1024):
                if not chunk:
                    continue
                total += len(chunk)
                if total > MAX_BYTES:
                    raise ValueError("EPG response exceeds 100 MB safety limit")
                chunks.append(chunk)

        xml_text = decode_xmltv_payload(b"".join(chunks))
        OUTPUT.parent.mkdir(parents=True, exist_ok=True)
        temp = OUTPUT.with_suffix(".xml.tmp")
        temp.write_text(xml_text, encoding="utf-8")
        temp.replace(OUTPUT)
        print(f"[OK] Saved validated XMLTV feed ({len(xml_text.encode('utf-8'))} bytes)")
        return 0
    except Exception as exc:
        # Do not print the source URL; it may contain a private access token.
        print(f"[ERROR] EPG download failed: {type(exc).__name__}: {exc}")
        return 1


if __name__ == "__main__":
    sys.exit(main())
