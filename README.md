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
- Optionally downloads an authorized XMLTV feed using the EPG_URL Actions variable.
- GitHub Actions runs every 30 minutes, on relevant pushes, or manually.

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
