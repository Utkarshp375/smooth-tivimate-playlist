# Smooth TiviMate Playlist

A GitHub Actions-based builder for combining public free-to-air M3U sources,
checking stream URL reachability, and optionally downloading an XMLTV EPG feed.

## Included public sources

The starter configuration uses community-maintained public playlists:
- India country playlist
- Gujarati-language playlist
- Hindi-language playlist
- Sports category playlist

The sources are listed in config/sources.txt and are merged with duplicate
stream URLs removed. Public streams can be geo-restricted, moved, or removed;
not every channel is guaranteed to play in every location.

## Features
- Combines remote HTTPS playlists and local .m3u/.m3u8 files in sources/.
- Preserves EXTINF and per-channel M3U directives such as EXTVLCOPT.
- Removes duplicate stream URLs.
- Checks stream reachability and writes checker_report.json and failed_urls.txt.
- Downloads an authorized XMLTV EPG feed when the GitHub Actions variable
  EPG_URL is configured.
- Runs after relevant pushes, manually, and every six hours.

## Add your own sources
Edit config/sources.txt and add one authorized HTTPS M3U URL per line.
Alternatively, place your own .m3u/.m3u8 files in sources/. Do not commit
passwords, cookies, account credentials, or temporary signed URLs.

## Run locally
Requires Python 3.10+.

    python -m pip install -r requirements.txt
    python -m unittest discover -s tests -v
    python scripts/build_playlist.py
    python scripts/check_links.py

## GitHub automatic updates
1. Open Settings -> Secrets and variables -> Actions -> Variables.
2. Add a repository variable named EPG_URL only if you have an authorized
   HTTPS XMLTV feed. Leave it unset to skip EPG download.
3. Open Actions -> Update TiviMate playlist -> Run workflow (or wait for the
   six-hour schedule).

## TiviMate URLs
After the first successful GitHub Actions run:

Playlist:
https://raw.githubusercontent.com/Utkarshp375/smooth-tivimate-playlist/main/output/smooth_playlist.m3u

EPG (only if configured and downloaded):
https://raw.githubusercontent.com/Utkarshp375/smooth-tivimate-playlist/main/output/epg.xml

## Important limitations
This project aggregates public playlist links; it does not host video. It does
not include JioTV, SonyLIV, FanCode, or other subscription-only streams and
does not refresh paid-service session tokens. Add such feeds only when you
have an official API or explicit redistribution authorization. The project
does not bypass DRM, authentication, subscriptions, or geographic restrictions.

A 401/403/404 result does not always mean a channel is permanently dead. The
checker reports status and never removes channels automatically. GitHub raw
hosting is static file hosting, not a media proxy.
