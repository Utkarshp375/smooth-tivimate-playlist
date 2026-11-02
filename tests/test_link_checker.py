import unittest
from scripts.check_links import sanitize_url


class SanitizeUrlTests(unittest.TestCase):
    def test_redacts_signed_stream_parameters(self):
        url = "https://cdn.example/live.m3u8?hdnea=secret&quality=hd&token=abc"
        safe = sanitize_url(url)
        self.assertNotIn("secret", safe)
        self.assertNotIn("abc", safe)
        self.assertIn("quality=hd", safe)
        self.assertIn("%5BREDACTED%5D", safe)

    def test_keeps_non_sensitive_query(self):
        self.assertEqual(
            sanitize_url("https://example.org/live?id=12"),
            "https://example.org/live?id=12",
        )


if __name__ == "__main__":
    unittest.main()
