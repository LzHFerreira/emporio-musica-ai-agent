import time
from datetime import timedelta
from unittest.mock import Mock
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from emporio.chat.lease import GENERATION
from emporio.chat.model_tracking import TrackedModelClient
from emporio.chat.models import Conversation, IncomingMessage


class TrackedModelDeadlineTests(TestCase):
    def make_job(self, deadline):
        now = timezone.now()
        conversation = Conversation.objects.create(sender="15550001111", last_customer_at=now)
        return IncomingMessage.objects.create(conversation=conversation, provider_id="deadline-job", sender=conversation.sender, text="question", state="running", received_at=now, occurred_at=now, deadline=deadline, worker_generation=GENERATION)

    def test_expired_work_stops_before_request_or_tool_counter(self):
        job = self.make_job(timezone.now() - timedelta(seconds=1))
        client = Mock(request_timeout=60)
        tracked = TrackedModelClient(job, client)
        with self.assertRaises(TimeoutError):
            tracked([], [])
        with self.assertRaises(TimeoutError):
            tracked.before_tool()
        job.refresh_from_db()
        self.assertEqual((job.model_requests, job.tool_executions), (0, 0))
        client.assert_not_called()

    def test_queue_warmup_reduces_timeout_and_restores_client_setting(self):
        job = self.make_job(timezone.now() + timedelta(seconds=5.4))
        seen = []
        class Client:
            model, returned_model, returned_provider = "qwen3:4b", "qwen3:4b", "ollama"
            request_timeout = 60
            def __call__(self, messages, tools):
                seen.append(self.request_timeout)
                return {"content": "ok"}
        client = Client()
        tracked = TrackedModelClient(job, client)
        time.sleep(0.05)
        self.assertEqual(tracked([], []), {"content": "ok"})
        job.refresh_from_db()
        self.assertTrue(0.1 < seen[0] < 0.4)
        self.assertEqual(client.request_timeout, 60)
        self.assertEqual((job.model_requests, job.requested_model, job.returned_provider), (1, "qwen3:4b", "ollama"))

    def test_late_model_output_is_rejected_after_deadline(self):
        job = self.make_job(timezone.now() + timedelta(seconds=5.4))
        class SlowClient:
            model, request_timeout = "qwen3:4b", 60
            def __call__(self, messages, tools):
                time.sleep(0.45)
                return {"content": "late"}
        with self.assertRaises(TimeoutError):
            TrackedModelClient(job, SlowClient())([], [])

    def test_slow_request_counter_write_stops_before_model_call(self):
        job = self.make_job(timezone.now() + timedelta(seconds=10))
        clock = [100.0]
        client = Mock(request_timeout=60)
        with patch("emporio.chat.model_tracking.monotonic", side_effect=lambda: clock[0]):
            tracked = TrackedModelClient(job, client)
            deadline = tracked._work_deadline
            tracked._increment = Mock(side_effect=lambda *args, **kwargs: clock.__setitem__(0, deadline + 0.01))
            with self.assertRaises(TimeoutError):
                tracked([], [])
        client.assert_not_called()

    def test_slow_tool_counter_write_is_rechecked_before_tool(self):
        job = self.make_job(timezone.now() + timedelta(seconds=10))
        clock = [100.0]
        with patch("emporio.chat.model_tracking.monotonic", side_effect=lambda: clock[0]):
            tracked = TrackedModelClient(job, Mock())
            deadline = tracked._work_deadline
            tracked._increment = Mock(side_effect=lambda *args, **kwargs: clock.__setitem__(0, deadline + 0.01))
            with self.assertRaises(TimeoutError):
                tracked.before_tool()

    def test_request_timeout_uses_time_remaining_after_counter_write(self):
        job = self.make_job(timezone.now() + timedelta(seconds=10))
        clock, seen = [100.0], []
        class Client:
            model, returned_model, returned_provider = "qwen3:4b", "qwen3:4b", "ollama"
            request_timeout = 60
            def __call__(self, messages, tools):
                seen.append(self.request_timeout)
                return {"content": "ok"}
        client = Client()
        with patch("emporio.chat.model_tracking.monotonic", side_effect=lambda: clock[0]):
            tracked = TrackedModelClient(job, client)
            tracked._increment = Mock(side_effect=lambda *args, **kwargs: clock.__setitem__(0, clock[0] + 2))
            self.assertEqual(tracked([], []), {"content": "ok"})
            self.assertAlmostEqual(seen[0], 3, delta=0.05)
        self.assertEqual(client.request_timeout, 60)

    def test_request_timeout_keeps_client_timeout_when_work_has_time(self):
        job = self.make_job(timezone.now() + timedelta(seconds=600))
        seen = []
        class Client:
            model, returned_model, returned_provider = "qwen3:4b", "qwen3:4b", "ollama"
            request_timeout = 180.0
            def __call__(self, messages, tools):
                seen.append(self.request_timeout)
                return {"content": "ok"}
        client = Client()
        tracked = TrackedModelClient(job, client)
        self.assertEqual(tracked([], []), {"content": "ok"})
        self.assertEqual(seen, [180.0])
        self.assertEqual(client.request_timeout, 180.0)
