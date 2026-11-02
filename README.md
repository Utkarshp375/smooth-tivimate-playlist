# Smooth TiviMate Playlist

A GitHub Actions-friendly toolkit to combine **authorized** M3U sources, validate stream URLs, and publish a TiviMate-ready playlist.

## What this starter does
- Combines local M3U files and/or public M3U URLs listed in `config/sources.txt`.
- Deduplicates entries by stream URL and preserves `tvg-id`, `tvg-name`, `tvg-logo`, and `group-title`.
- Checks URLs with bounded HTTP requests and writes a JSON report. It does **not** silently remove failures.
- Publishes `output/smooth_playlist.m3u` and an XMLTV file if you provide an authorized EPG source.
- Runs on a schedule using GitHub Actions.

## Important source/rights note
This project is a playlist processor, not a source provider. Add only streams and EPG feeds you are authorized to access and redistribute. Do not commit account cookies, private tokens, DRM keys, or paid-service credentials. It does not bypass DRM, authentication, geo-restrictions, or provider access controls.

## Quick start
1. Put authorized `.m3u`/`.m3u8` files in `sources/`.
2. Edit `config/sources.txt`; one local path or HTTPS playlist URL per line.
3. Optionally set `EPG_URL` as a GitHub Actions repository variable to an authorized XMLTV feed URL.
4. Run locally:
   ```bash
   python -m pip install -r requirements.txt
   python scripts/build_playlist.py
   python scripts/check_links.py
   ```
5. Commit and push. The workflow rebuilds every 6 hours and commits changed output.

## TiviMate URLs after enabling GitHub Pages
Raw playlist:
`https://raw.githubusercontent.com/OWNER/smooth-tivimate-playlist/main/output/smooth_playlist.m3u`

Raw EPG:
`https://raw.githubusercontent.com/OWNER/smooth-tivimate-playlist/main/output/epg.xml`

Replace `OWNER` with your GitHub username. These links work only after the repository exists and output files have been committed.

## Proxy and EPG
GitHub Pages/Raw GitHub serves static files; it is **not** a streaming proxy. A proxy must be deployed separately (for example, a secured Cloudflare Worker or your own server) and must only relay sources you are authorized to use. See `proxy/README.md`.
EPG output is not invented: configure an authorized XMLTV feed. If none is configured, no fake programme schedule is generated.

## Reports
- `output/checker_report.json`: per-URL status, response time and error.
- `output/failed_urls.txt`: URLs needing review.
- Link checks can return 403/404 for expiring, authenticated, region-limited, or temporarily unavailable streams; inspect the source/provider before treating a result as permanent.
