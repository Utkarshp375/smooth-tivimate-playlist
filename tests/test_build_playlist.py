import unittest

from scripts.build_playlist import parse_m3u


class ParseM3UTests(unittest.TestCase):
    def test_preserves_channel_tags(self):
        source = """#EXTM3U
#EXTINF:-1 tvg-id="news" group-title="News",Example News
#EXTVLCOPT:http-user-agent=ExamplePlayer
https://example.com/live.m3u8
"""
        entries = parse_m3u(source, "test-source")
        self.assertEqual(len(entries), 1)
        metadata, url = entries[0]
        self.assertEqual(metadata[0], '#EXTINF:-1 tvg-id="news" group-title="News",Example News')
        self.assertEqual(metadata[1], "#EXTVLCOPT:http-user-agent=ExamplePlayer")
        self.assertEqual(url, "https://example.com/live.m3u8")

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
        self.assertEqual([entry[1] for entry in entries],
                         ["https://example.com/one", "https://example.com/two"])


if __name__ == "__main__":
    unittest.main()
