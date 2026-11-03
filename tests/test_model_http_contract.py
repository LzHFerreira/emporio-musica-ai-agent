import threading
import time
from unittest.mock import patch

import httpx
from django.test import SimpleTestCase

from emporio.chat.model_http import post_with_timeout


class SlowClient:
    def __init__(self):
        self.started, self.release, self.calls = threading.Event(), threading.Event(), 0

    def post(self, *args, **kwargs):
        self.calls += 1
        self.started.set()
        self.release.wait()
        return httpx.Response(200, json={"ok": True})


class ModelHttpContractTests(SimpleTestCase):
    def test_wall_deadline_discards_late_response_without_retry(self):
        client = SlowClient()
        started = time.monotonic()
        try:
            with self.assertRaises(httpx.TimeoutException):
                post_with_timeout(client, "http://model.test", headers={}, payload={}, timeout=0.02)
        finally:
            client.release.set()
        self.assertTrue(client.started.is_set())
        self.assertEqual(client.calls, 1)
        self.assertLess(time.monotonic() - started, 0.25)

    def test_timeout_is_clamped_and_redirects_are_disabled(self):
        seen = []
        class Client:
            def post(self, *args, **kwargs):
                seen.append(kwargs)
                return httpx.Response(200)
        response = post_with_timeout(Client(), "http://model.test", headers={}, payload={}, timeout=61)
        self.assertEqual(response.status_code, 200)
        self.assertEqual((seen[0]["timeout"], seen[0]["follow_redirects"]), (60, False))

    def test_nonpositive_deadline_never_starts_transport(self):
        client = SlowClient()
        with self.assertRaises(httpx.TimeoutException):
            post_with_timeout(client, "http://model.test", headers={}, payload={}, timeout=0)
        self.assertEqual(client.calls, 0)

    def test_transport_exception_propagates_without_retry(self):
        class Client:
            calls = 0
            def post(self, *args, **kwargs):
                self.calls += 1
                raise RuntimeError("synthetic transport failure")
        client = Client()
        with self.assertRaisesRegex(RuntimeError, "synthetic transport failure"):
            post_with_timeout(client, "http://model.test", headers={}, payload={}, timeout=1)
        self.assertEqual(client.calls, 1)

    def test_response_arriving_after_deadline_is_discarded(self):
        client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200)))
        with patch("emporio.chat.model_http.monotonic", side_effect=[0, 0, 2]):
            with self.assertRaises(httpx.TimeoutException):
                post_with_timeout(client, "http://model.test", headers={}, payload={}, timeout=1)
        client.close()
