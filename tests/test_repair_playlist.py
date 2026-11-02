import unittest

from scripts.repair_playlist import channel_key, repairable, read_entries


class RepairPlaylistTests(unittest.TestCase):
    def test_prefers_tvg_id_for_channel_matching(self):
        first = ['#EXTINF:-1 tvg-id="gujarat.news" group-title="News",News One']
        second = ['#EXTINF:-1 tvg-id="gujarat.news" group-title="Regional",Gujarati News']
        self.assertEqual(channel_key(first), channel_key(second))

    def test_normalizes_quality_suffix_for_name_matching(self):
        hd = ['#EXTINF:-1 group-title="News",Example News HD']
        sd = ['#EXTINF:-1 group-title="News",Example-News SD']
        self.assertEqual(channel_key(hd), channel_key(sd))

    def test_repair_only_dead_or_transient_server_errors(self):
        self.assertTrue(repairable({"status": "not_found", "http_status": 404}))
        self.assertTrue(repairable({"status": "error", "http_status": None}))
        self.assertTrue(repairable({"status": "http_error", "http_status": 503}))
        self.assertFalse(repairable({"status": "restricted", "http_status": 403}))
        self.assertFalse(repairable({"status": "http_error", "http_status": 429}))
        self.assertFalse(repairable({"status": "reachable", "http_status": 200}))

    def test_reads_only_safe_source_entries(self):
        source = """#EXTM3U
#EXTINF:-1 tvg-id="safe",Safe Channel
https://example.com/safe.m3u8
#EXTINF:-1 tvg-id="signed",Signed Channel
https://example.com/live.m3u8?__hdnea__=secret
"""
        entries = read_entries(source)
        self.assertEqual([url for _, url in entries], ["https://example.com/safe.m3u8"])


if __name__ == "__main__":
    unittest.main()
