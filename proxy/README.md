# Proxy notes

GitHub Pages and raw GitHub URLs are static file hosting; they are not a stream
proxy and cannot refresh provider tokens.

A proxy should only forward streams that you own or are explicitly authorized
to redistribute. If you deploy one, use a strict server-side allowlist of
approved hostnames, HTTPS-only upstreams, request timeouts, response-size
limits, and rate limits. Never create an open proxy or accept arbitrary target
URLs from playlist users.

This repository intentionally does not implement DRM, login, cookie, token,
or geo-restriction bypass. Expiring signed stream URLs must be refreshed using
the provider's documented and authorized API or official app.
