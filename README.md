# Smooth TiviMate Playlist

Combines public/authorized M3U sources, removes duplicates, preserves safe player
format metadata, reports HTTP reachability and optionally downloads an authorized
XMLTV EPG feed.

## Sources
- sportlive18/All-Playlist upstream combined M3U
- India, Gujarati, Hindi and Sports public playlists from iptv-org
- Authorized .m3u/.m3u8 files placed in sources/

## Playback metadata and safety
The builder preserves harmless compatibility hints: DASH manifest type for
public, unencrypted .mpd manifests, and VLC User-Agent/Referrer options.
It rejects cookies, custom HTTP header blobs, DRM license keys, signed/expiring
URLs, and subscription-service labels/hosts (FanCode, SonyLIV, Jio Hotstar,
Prime Video, Willow, Zee5, etc.).

It does not generate tokens, retrieve account cookies, proxy paid streams, or
bypass DRM, subscriptions, authentication or geographic restrictions. Use only
streams you are authorized to access and redistribute. A .mpd URL is not
automatically playable merely because a manifest hint is present.

## Features
- Fetches upstream M3U sources and local .m3u/.m3u8 files.
- Preserves safe EXTINF and supported player compatibility metadata.
- Adds DASH manifest hints to public .mpd URLs.
- Removes duplicate stream URLs.
- Writes output/checker_report.json and output/failed_urls.txt.
- Writes output/expiry_report.json when a URL exposes an `exp=` Unix timestamp. It shows expiry in UTC/IST and a countdown without storing the cookie value.
- Writes output/restricted_channels.json for HTTP 401/403 channels, with sensitive query values redacted.
- Can replace dead links only when an exact same-channel alternative from configured authorized sources is verified reachable.
- Optionally downloads an authorized XMLTV feed using the EPG_URL Actions variable.
- GitHub Actions polls every 5 minutes (GitHub schedule; best-effort), on relevant pushes, or manually. Each run downloads the latest content from every configured HTTPS M3U source and rebuilds the playlist, so updated source entries are picked up on the next successful run. Transient upstream errors, including HTTP 429/5xx, are retried with backoff before a source is skipped. GitHub can delay or drop scheduled runs during high load, so this is not an instant webhook. Account-bound tokens and 401/403 restrictions are not renewed or bypassed.

## Run locally
    python -m pip install -r requirements.txt
    python -m unittest discover -s tests -v
    python scripts/build_playlist.py
    python scripts/check_links.py

## TiviMate playlist
https://raw.githubusercontent.com/Utkarshp375/smooth-tivimate-playlist/main/output/smooth_playlist.m3u

GitHub raw hosting serves the playlist file; it is not a video proxy. The checker
tests reachability, not successful playback. 401/403/404 can indicate expired
or restricted sources; failed links are reported, not automatically deleted.

## EPG
The scheduled workflow uses the public India XMLTV feed `https://iptv-epg.org/files/epg-in.xml.gz` unless Actions variable `EPG_URL` overrides it. The publisher currently lists 275 Indian channels and 58,581 programmes; coverage and freshness can change. Gujarati/Hindi coverage is not guaranteed for every channel. EPG matching requires playlist `tvg-id` to equal an XMLTV channel ID.

TiviMate EPG URL:
`https://raw.githubusercontent.com/Utkarshp375/smooth-tivimate-playlist/main/output/epg.xml`

## Authorized proxy
A Cloudflare Worker template is in `proxy/worker.js`; it is not deployed yet. You must provide exact HTTPS hostnames you own or are authorized to relay and configure Cloudflare secrets. See `proxy/README.md`. Never commit proxy credentials or private source URLs into this public repository.
