from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from emporio.agent_protocol import FAILURE_TEXT
from emporio.catalog.models import SourceSnapshot
from emporio.chat.models import Conversation, IncomingMessage, WorkerLease
from emporio.chat.webhook import UNSUPPORTED_TEXT
from emporio.chat.worker import process_next

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class WorkerStateContractTests(TestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)
        self.version = SourceSnapshot.objects.get(is_active=True).version

    def enqueue(self, *, deadline=None, text="Qual o horário da loja?", state="pending"):
        now = timezone.now()
        conversation = Conversation.objects.create(sender=f"5567998123{IncomingMessage.objects.count():04d}", last_customer_at=now)
        return IncomingMessage.objects.create(
            conversation=conversation, provider_id=f"wamid.worker.{IncomingMessage.objects.count()}",
            sender=conversation.sender, text=text, state=state, received_at=now,
            occurred_at=now, deadline=deadline or now + timedelta(seconds=60), snapshot_version=self.version,
        )

    def test_expired_turn_remains_operator_visible_as_notification_pending(self):
        job = self.enqueue(deadline=timezone.now() - timedelta(seconds=1))
        model, send = Mock(), Mock()
        process_next(model_client=model, send_client=send)
        job.refresh_from_db()
        self.assertEqual(job.state, "notification_pending")
        self.assertTrue(job.notification_only)
        model.assert_not_called()

    def test_model_attempt_counter_is_durable_before_callback_raises(self):
        job = self.enqueue()
        observed = []
        def fail(messages, tools):
            job.refresh_from_db()
            observed.append(job.model_requests)
            raise RuntimeError("provider unavailable")
        process_next(model_client=fail, send_client=Mock(return_value="wamid.fallback"))
        job.refresh_from_db()
        self.assertEqual((observed, job.model_requests), ([1], 1))

    def test_unsupported_message_gets_fixed_reply_without_model_call(self):
        job = self.enqueue(text=UNSUPPORTED_TEXT)
        model = Mock()
        reply = process_next(model_client=model, send_client=Mock(return_value="wamid.unsupported"))
        self.assertEqual(reply.text, UNSUPPORTED_TEXT)
        model.assert_not_called()

    def test_active_worker_lease_prevents_a_second_process_from_claiming(self):
        job = self.enqueue()
        now = timezone.now()
        WorkerLease.objects.create(key="default", generation="other-process", expires_at=now + timedelta(seconds=5), renewed_at=now)
        model, send = Mock(), Mock()
        self.assertIsNone(process_next(model_client=model, send_client=send))
        job.refresh_from_db()
        self.assertEqual(job.state, "pending")
        model.assert_not_called()
        send.assert_not_called()

    def test_missing_active_source_uses_fixed_fallback_without_model_call(self):
        self.enqueue()
        SourceSnapshot.objects.update(is_active=False)
        model = Mock()
        reply = process_next(model_client=model, send_client=Mock(return_value="wamid.fallback"))
        self.assertEqual((reply.text, reply.state), (FAILURE_TEXT, "accepted"))
        model.assert_not_called()

    def test_unknown_send_outcome_is_not_retried_on_worker_restart(self):
        self.enqueue()
        model = Mock(return_value={"content": '{"outcome":"answer","text":"Olá!","reason":null}'})
        send = Mock(side_effect=TimeoutError("acceptance unknown"))
        reply = process_next(model_client=model, send_client=send)
        self.assertEqual(reply.state, "unknown")
        self.assertIsNone(process_next(model_client=Mock(), send_client=send))
        self.assertEqual((send.call_count, model.call_count), (1, 1))
