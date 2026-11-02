# Usage

## Add a remote playlist
Put its HTTPS URL on a new line in config/sources.txt.

## Add a local playlist
Place .m3u or .m3u8 files in sources/. Do not add files containing credentials
or private session data.

## Build
Run python scripts/build_playlist.py. The result is output/smooth_playlist.m3u.

## Check links
Run python scripts/check_links.py. Review output/checker_report.json and
output/failed_urls.txt. A 401/403 can indicate authorization, region, or an
expiring token; it is not automatically a dead channel.

## EPG
Set the GitHub Actions repository variable EPG_URL to an authorized HTTPS XMLTV
feed. See EPG.md.
