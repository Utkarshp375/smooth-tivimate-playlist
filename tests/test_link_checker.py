import unittest
from scripts.check_links import extract_expiry, sanitize_url


class SanitizeUrlTests(unittest.TestCase):
    def test_redacts_signed_stream_parameters(self):
        url = "https://cdn.example/live.m3u8?hdnea=secret&quality=hd&token=abc"
        safe = sanitize_url(url)
        self.assertNotIn("secret", safe)
        self.assertNotIn("abc", safe)
        self.assertIn("quality=hd", safe)
        self.assertIn("%5BREDACTED%5D", safe)

    def test_redacts_underscored_hdnea_parameter(self):
        safe = sanitize_url("https://cdn.example/a.mpd?__hdnea__=private")
        self.assertNotIn("private", safe)

    def test_keeps_non_sensitive_query(self):
        self.assertEqual(
            sanitize_url("https://example.org/live?id=12"),
            "https://example.org/live?id=12",
        )


class ExpiryAuditTests(unittest.TestCase):
    def test_reads_expiry_from_embedded_hdnea_cookie(self):
        result = extract_expiry(
            "https://cdn.example/a.mpd?__hdnea__=st=1700000000~exp=1800000000~acl=/a/*",
            now=1799990000,
        )
        self.assertEqual(result["expiry_status"], "expiring_within_24h")
        self.assertEqual(result["expiry_unix"], 1800000000)
        self.assertEqual(result["seconds_remaining"], 10000)
        self.assertIsNotNone(result["expiry_ist"])

    def test_expired_token(self):
        result = extract_expiry("https://cdn.example/a?exp=1700000000", now=1800000000)
        self.assertEqual(result["expiry_status"], "expired")

    def test_unknown_when_no_exp_parameter(self):
        result = extract_expiry("https://cdn.example/a?id=42", now=1800000000)
        self.assertEqual(result["expiry_status"], "unknown")
        self.assertIsNone(result["expiry_unix"])


if __name__ == "__main__":
    unittest.main()
