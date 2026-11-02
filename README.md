# Smooth TiviMate Playlist

A GitHub Actions playlist builder that combines public community M3U sources,
removes duplicates, filters protected/temporary links, checks reachability and
optionally downloads an authorized XMLTV EPG feed.

## Sources

- sportlive18/All-Playlist upstream combined M3U (fetched fresh on each run)
- India, Gujarati, Hindi and Sports public playlists from iptv-org

The sportlive18 feed is treated as untrusted input. Entries containing DRM or
ClearKey directives, cookies, expiring/signed URL parameters, or labels/hosts
for subscription services (FanCode, SonyLIV, Jio Hotstar, Prime Video, Willow,
Zee5, etc.) are excluded. This avoids copying session credentials or protected
streams into this repository. This filter is conservative and may exclude
legitimate channels that happen to use similar labels or URL parameters.

This project does not generate stream URLs, retrieve account cookies, bypass
DRM, subscriptions, authentication or geographic restrictions. Use only streams
you are authorized to access and redistribute.

## Features

- Fetches upstream M3U sources and local .m3u/.m3u8 files in sources/.
- Preserves safe EXTINF and non-authentication metadata.
- Filters cookie, DRM/ClearKey, subscription-labelled and expiring-token entries.
- Removes duplicate stream URLs.
- Checks links and writes output/checker_report.json and output/failed_urls.txt.
- Optionally downloads an authorized XMLTV feed when the Actions variable
  EPG_URL is configured.
- GitHub Actions runs every 30 minutes, on relevant pushes, or manually.

## Add local sources

Place authorized .m3u/.m3u8 files in sources/. Do not commit passwords, cookies,
account credentials, DRM keys or temporary signed URLs.

## Run locally

Requires Python 3.10+.

    python -m pip install -r requirements.txt
    python -m unittest discover -s tests -v
    python scripts/build_playlist.py
    python scripts/check_links.py

## EPG

To enable EPG, add a repository variable named EPG_URL at:
Settings -> Secrets and variables -> Actions -> Variables.
Use only an authorized HTTPS XMLTV feed. If unset, EPG download is skipped.

## TiviMate URLs

Playlist (available after a successful Actions run):
https://raw.githubusercontent.com/Utkarshp375/smooth-tivimate-playlist/main/output/smooth_playlist.m3u

EPG (only if configured and downloaded):
https://raw.githubusercontent.com/Utkarshp375/smooth-tivimate-playlist/main/output/epg.xml

## Notes

GitHub raw hosting serves the generated playlist file; it is not a video proxy.
A 401/403/404 can indicate an expired or restricted source, not necessarily a
permanently dead channel. The checker reports status and does not delete
channels automatically.
