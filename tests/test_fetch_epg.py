import gzip
import unittest

from scripts.fetch_epg import decode_xmltv_payload


class EpgPayloadTests(unittest.TestCase):
    def test_decodes_plain_xmltv(self):
        payload = b'<?xml version="1.0"?><tv><channel id="x"/></tv>'
        self.assertIn("<tv>", decode_xmltv_payload(payload))

    def test_decodes_gzip_xmltv(self):
        payload = gzip.compress(b'<?xml version="1.0"?><tv><channel id="x"/></tv>')
        self.assertIn("<channel", decode_xmltv_payload(payload))

    def test_rejects_non_xmltv_root(self):
        with self.assertRaises(ValueError):
            decode_xmltv_payload(b"<html></html>")

    def test_enforces_decompressed_size_limit(self):
        payload = gzip.compress(b"<tv>" + (b"x" * 1000) + b"</tv>")
        with self.assertRaises(ValueError):
            decode_xmltv_payload(payload, max_bytes=100)


if __name__ == "__main__":
    unittest.main()
