from io import StringIO
from types import SimpleNamespace
from unittest.mock import Mock, patch
from datetime import timedelta

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from emporio.chat.models import Conversation, IncomingMessage, OutgoingReply, WorkerLease


@override_settings(MODEL_PROVIDER="openrouter")
class ChatWorkerCommandContractTests(TestCase):
    def test_worker_refuses_to_start_without_each_required_credential(self):
        with override_settings(OPENROUTER_API_KEY="", META_API_TOKEN="token"):
            with self.assertRaises(CommandError):
                call_command("chat_worker", once=True)

    @override_settings(OPENROUTER_API_KEY="", META_API_TOKEN="token")
    def test_missing_model_key_leaves_stale_work_and_lease_untouched(self):
        job, reply = self.stale_work("expired-generation", expired=True)
        with self.assertRaises(CommandError):
            call_command("chat_worker", once=True)
        job.refresh_from_db()
        self.assertEqual((job.state, reply.state), ("running", "sending"))
        self.assertEqual(WorkerLease.objects.get().generation, "expired-generation")
        with override_settings(OPENROUTER_API_KEY="key", META_API_TOKEN=""):
            with self.assertRaises(CommandError):
                call_command("chat_worker", once=True)

    @override_settings(OPENROUTER_API_KEY="key", META_API_TOKEN="token")
    def test_once_processes_one_reply_and_closes_both_clients(self):
        model_client, meta_client = Mock(), Mock()
        with patch("emporio.chat.management.commands.chat_worker.create_model_client", return_value=model_client), patch("emporio.chat.management.commands.chat_worker.MetaClient", return_value=meta_client), patch("emporio.chat.management.commands.chat_worker.process_next", return_value=SimpleNamespace(state="accepted")) as process:
            output = StringIO()
            call_command("chat_worker", once=True, stdout=output)
        process.assert_called_once_with(model_client=model_client, send_client=meta_client)
        self.assertIn("reply_state=accepted", output.getvalue())
        model_client.client.close.assert_called_once()
        meta_client.client.close.assert_called_once()

    @override_settings(OPENROUTER_API_KEY="key", META_API_TOKEN="token")
    def test_continuous_worker_stops_on_interrupt_and_closes_provider_clients(self):
        model_client, meta_client = Mock(), Mock()
        with patch("emporio.chat.management.commands.chat_worker.create_model_client", return_value=model_client), patch("emporio.chat.management.commands.chat_worker.MetaClient", return_value=meta_client), patch("emporio.chat.management.commands.chat_worker.process_next", return_value=None) as process, patch("emporio.chat.management.commands.chat_worker.time.sleep", side_effect=KeyboardInterrupt):
            call_command("chat_worker")
        process.assert_called_once_with(model_client=model_client, send_client=meta_client)
        model_client.client.close.assert_called_once()
        meta_client.client.close.assert_called_once()

    @override_settings(OPENROUTER_API_KEY="key", META_API_TOKEN="token")
    def test_startup_recovery_interrupts_expired_generation_before_worker_iteration(self):
        job, reply = self.stale_work("old-generation", expired=True)
        with patch("emporio.chat.management.commands.chat_worker.create_model_client"), patch("emporio.chat.management.commands.chat_worker.MetaClient"), patch("emporio.chat.management.commands.chat_worker.process_next", return_value=None) as process:
            call_command("chat_worker", once=True)
        job.refresh_from_db()
        reply.refresh_from_db()
        self.assertEqual((job.state, reply.state), ("interrupted", "unknown"))
        process.assert_called_once()

    @override_settings(OPENROUTER_API_KEY="key", META_API_TOKEN="token")
    def test_active_foreign_generation_blocks_startup_without_recovery_or_claim(self):
        job, reply = self.stale_work("active-generation", expired=False)
        with patch("emporio.chat.management.commands.chat_worker.create_model_client") as model, patch("emporio.chat.management.commands.chat_worker.MetaClient") as sender, patch("emporio.chat.management.commands.chat_worker.process_next") as process:
            with self.assertRaises(CommandError):
                call_command("chat_worker", once=True)
        job.refresh_from_db()
        reply.refresh_from_db()
        self.assertEqual((job.state, reply.state), ("running", "sending"))
        model.assert_not_called()
        sender.assert_not_called()
        process.assert_not_called()

    def stale_work(self, generation, *, expired):
        now = timezone.now()
        expiry = now - timedelta(seconds=1) if expired else now + timedelta(seconds=5)
        WorkerLease.objects.create(key="default", generation=generation, expires_at=expiry, renewed_at=now)
        conversation = Conversation.objects.create(sender=f"1555000{IncomingMessage.objects.count():04d}", last_customer_at=now)
        job = IncomingMessage.objects.create(
            conversation=conversation, provider_id="wamid.stale", sender=conversation.sender,
            text="question", state="running", received_at=now, occurred_at=now,
            deadline=now + timedelta(seconds=60), snapshot_version="snapshot-a", worker_generation=generation,
        )
        reply = OutgoingReply.objects.create(source=job, text="draft", state="sending")
        return job, reply

    @override_settings(MODEL_PROVIDER="ollama", OPENROUTER_API_KEY="", META_API_TOKEN="token", OLLAMA_BASE_URL="http://localhost:11434/v1", OLLAMA_MODEL="qwen3:4b")
    def test_worker_selects_and_closes_local_provider_without_cloud_key(self):
        model_client, meta_client = Mock(), Mock()
        with patch("emporio.chat.management.commands.chat_worker.create_model_client", return_value=model_client) as local, patch("emporio.chat.management.commands.chat_worker.MetaClient", return_value=meta_client), patch("emporio.chat.management.commands.chat_worker.process_next", return_value=None):
            call_command("chat_worker", once=True)
        local.assert_called_once_with()
        model_client.client.close.assert_called_once()
        meta_client.client.close.assert_called_once()
