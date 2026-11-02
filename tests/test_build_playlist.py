import unittest
from scripts.build_playlist import parse_m3u

class ParseM3UTests(unittest.TestCase):
    def test_preserves_safe_channel_tags(self):
        source = """#EXTM3U
#EXTINF:-1 tvg-id="news" group-title="News",Example News
#EXTVLCOPT:http-user-agent=ExamplePlayer
https://example.com/live.m3u8
"""
        entries = parse_m3u(source, "test-source")
        self.assertEqual(len(entries), 1)
        self.assertEqual(entries[0][0][1], "#EXTVLCOPT:http-user-agent=ExamplePlayer")
        self.assertEqual(entries[0][1], "https://example.com/live.m3u8")

    def test_adds_fallback_metadata_without_extinf(self):
        entries = parse_m3u("https://example.com/a.m3u8\n", "Local Source")
        self.assertEqual(entries[0][0], ['#EXTINF:-1 group-title="Other",Local Source'])

    def test_multiple_channels_are_separated(self):
        source = """#EXTM3U
#EXTINF:-1,One
https://example.com/one
#EXTINF:-1,Two
https://example.com/two
"""
        entries = parse_m3u(source, "test")
        self.assertEqual([x[1] for x in entries], ["https://example.com/one", "https://example.com/two"])

    def test_rejects_cookie_and_license_entries(self):
        source = """#EXTM3U
#EXTINF:-1,Cookie
#EXTVLCOPT:http-cookie=secret
https://example.com/cookie.m3u8
#EXTINF:-1,DRM
#KODIPROP:inputstream.adaptive.license_key=abc:def
https://example.com/drm.mpd
#EXTINF:-1,Clean
https://example.com/clean.m3u8
"""
        entries = parse_m3u(source, "upstream")
        self.assertEqual([x[1] for x in entries], ["https://example.com/clean.m3u8"])

    def test_adds_dash_manifest_hints_without_license(self):
        entries = parse_m3u("#EXTINF:-1,Public DASH\nhttps://example.com/live.mpd\n", "upstream")
        self.assertEqual(len(entries), 1)
        self.assertIn("#KODIPROP:inputstream=inputstream.adaptive", entries[0][0])
        self.assertIn("#KODIPROP:inputstream.adaptive.manifest_type=mpd", entries[0][0])

    def test_filters_subscription_and_signed_urls(self):
        source = """#EXTM3U
#EXTINF:-1 group-title="SonyLIV",Live Match
https://example.com/live.m3u8
#EXTINF:-1,Temporary
https://example.com/live.m3u8?hdnea=secret
#EXTINF:-1,Stable
https://example.com/stable.m3u8
"""
        entries = parse_m3u(source, "upstream")
        self.assertEqual([x[1] for x in entries], ["https://example.com/stable.m3u8"])

    def test_filters_jio_style_wrapped_hdnea_and_other_signed_tokens(self):
        source = """#EXTM3U
#EXTINF:-1,Signed DASH
https://example.com/live.mpd?__hdnea__=secret
#EXTINF:-1,Signed HLS
https://example.com/live.m3u8?__hdntl__=secret
#EXTINF:-1,Akamaized token
https://example.com/live.m3u8?hdnts=secret
#EXTINF:-1,Stable DASH
https://example.com/free/live.mpd
"""
        entries = parse_m3u(source, "upstream")
        self.assertEqual([x[1] for x in entries], ["https://example.com/free/live.mpd"])
        self.assertIn("#KODIPROP:inputstream.adaptive.manifest_type=mpd", entries[0][0])

if __name__ == "__main__":
    unittest.main()
