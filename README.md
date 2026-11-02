# Smooth TiviMate Playlist

A GitHub Actions-based builder for combining authorized M3U/M3U8 sources,
checking stream URL reachability, and optionally downloading an XMLTV EPG feed.

## Features
- Combines remote HTTPS playlists listed in config/sources.txt and local
  .m3u/.m3u8 files placed in sources/.
- Preserves EXTINF metadata and removes duplicate stream URLs.
- Checks URLs and writes a JSON report plus a list of non-reachable URLs.
- Downloads an authorized XMLTV feed when the GitHub Actions variable EPG_URL
  is configured.
- Runs manually or every six hours using GitHub Actions.

## Add playlist sources
Edit config/sources.txt and add one authorized HTTPS playlist URL per line.
Alternatively, add your own M3U files to sources/. Do not commit passwords,
cookies, account credentials, or temporary signed URLs.

## Run locally
Requires Python 3.10+.

    python -m pip install -r requirements.txt
    python scripts/build_playlist.py
    python scripts/check_links.py

## GitHub automatic updates
1. Open Settings -> Secrets and variables -> Actions -> Variables.
2. Add EPG_URL only if you have an authorized XMLTV feed.
3. Open Actions -> Update TiviMate playlist -> Run workflow.

The workflow also runs every six hours and commits generated output when changed.

## TiviMate URLs
After the first successful workflow run:

Playlist:
https://raw.githubusercontent.com/Utkarshp375/smooth-tivimate-playlist/main/output/smooth_playlist.m3u

EPG (only if configured and downloaded):
https://raw.githubusercontent.com/Utkarshp375/smooth-tivimate-playlist/main/output/epg.xml

## Limitations
This is a playlist aggregation framework, not a source provider. No JioTV,
SonyLIV, FanCode, or other paid stream URLs are bundled. Signed URLs can expire;
401/403/404 does not always prove a stream is permanently dead. The checker
reports status and never removes channels automatically.

The project does not bypass DRM, authentication, subscriptions, or geographic
restrictions. Use only streams and EPG feeds you are authorized to access and
redistribute. GitHub raw hosting is static hosting, not a media proxy.
