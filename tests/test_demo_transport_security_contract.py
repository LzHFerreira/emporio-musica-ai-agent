"""The signed webhook helper must reject non-loopback destinations before I/O."""

from unittest.mock import patch

from django.test import SimpleTestCase

from emporio.chat.demo_http import signed_post


class SignedPostDestinationTests(SimpleTestCase):
    def test_file_and_external_urls_are_rejected_without_opening_them(self):
        with patch("emporio.chat.demo_http.httpx.post") as post:
            for url in ("file:///tmp/should-not-open", "https://external.example/hook"):
                with self.subTest(url=url), self.assertRaises(ValueError):
                    signed_post(url, {"object": "test"}, "secret")
            post.assert_not_called()
