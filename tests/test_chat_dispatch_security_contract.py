import json
from datetime import timedelta
from pathlib import Path
from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import TestCase
from django.utils import timezone

from emporio.agent_protocol import FAILURE_TEXT
from emporio.catalog.models import SourceSnapshot
from emporio.chat.dispatch import dispatch
from emporio.chat.lease import acquire
from emporio.chat.models import Conversation, IncomingMessage, OutgoingReply
from emporio.chat.worker import process_next
from emporio.orders.models import Customer

DATA_DIR = Path(__file__).resolve().parents[1] / "data"


class DispatchSecurityContractTests(TestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)
        self.snapshot = SourceSnapshot.objects.get(is_active=True)
        self.now = timezone.now()

    def make_reply(self, sender=None):
        sender = sender or f"5567998123{IncomingMessage.objects.count():04d}"
        conversation = Conversation.objects.create(sender=sender, last_customer_at=self.now)
        job = IncomingMessage.objects.create(
            conversation=conversation, provider_id=f"wamid.dispatch.{IncomingMessage.objects.count()}", sender=conversation.sender,
            text="Pergunta", state="completed", received_at=self.now, occurred_at=self.now,
            deadline=self.now + timedelta(seconds=60), snapshot_version=self.snapshot.version,
        )
        return OutgoingReply.objects.create(source=job, text="Resposta validada", state="queued")

    def assert_withheld(self, reply):
        sender = Mock(return_value="wamid.should-not-send")
        acquire()
        dispatch(reply, sender)
        sender.assert_not_called()
        reply.refresh_from_db()
        self.assertNotIn(reply.state, {"sending", "accepted", "delivered", "read"})

    def test_takeover_between_draft_and_dispatch_suppresses_bot_reply(self):
        reply = self.make_reply()
        Conversation.objects.filter(pk=reply.source.conversation_id).update(mode="human_pending")
        self.assert_withheld(reply)

    def test_active_source_change_between_draft_and_dispatch_suppresses_stale_reply(self):
        reply = self.make_reply()
        self.snapshot.is_active = False
        self.snapshot.save(update_fields=["is_active"])
        SourceSnapshot.objects.create(version="new-active", manifest={}, pricing_rule_version="v2", pix_basis_points=500, is_active=True)
        sender = Mock(return_value="wamid.safe-fallback")
        acquire()
        dispatch(reply, sender)
        self.assertEqual(sender.call_args.args[0].text, FAILURE_TEXT)

    def test_expired_service_window_and_deadline_suppress_free_form_send(self):
        reply = self.make_reply()
        Conversation.objects.filter(pk=reply.source.conversation_id).update(last_customer_at=self.now - timedelta(hours=25))
        self.assert_withheld(reply)
        reply = self.make_reply()
        IncomingMessage.objects.filter(pk=reply.source_id).update(deadline=self.now - timedelta(seconds=1))
        self.assert_withheld(reply)

    def test_takeover_and_source_change_during_model_call_prevent_dispatch(self):
        for change in ("takeover", "source"):
            with self.subTest(change=change):
                reply = self.make_reply()
                job = reply.source
                reply.delete()
                IncomingMessage.objects.filter(pk=job.pk).update(state="pending")
                def draft(*args, **kwargs):
                    if change == "takeover":
                        Conversation.objects.filter(pk=job.conversation_id).update(mode="human_pending")
                    else:
                        SourceSnapshot.objects.filter(pk=self.snapshot.pk).update(is_active=False)
                        SourceSnapshot.objects.create(version=f"new-{job.pk}", manifest={}, pricing_rule_version="v2", pix_basis_points=500, is_active=True)
                    return {"outcome": "answer", "text": "Resposta antiga", "reason": None, "sources": [], "operations": [], "model_requests": 1, "tool_executions": 0, "snapshot_version": job.snapshot_version}
                sender = Mock(return_value="wamid.safe-fallback")
                with patch("emporio.chat.worker.run_turn", side_effect=draft):
                    process_next(model_client=Mock(), send_client=sender)
                if change == "takeover":
                    sender.assert_not_called()
                else:
                    self.assertEqual(sender.call_args.args[0].text, FAILURE_TEXT)

    def test_changed_customer_binding_after_order_lookup_withholds_tracking_data(self):
        reply = self.make_reply("5567998123456")
        job = reply.source
        reply.delete()
        customer = Customer.objects.get(snapshot=self.snapshot, source_id=1)
        IncomingMessage.objects.filter(pk=job.pk).update(
            state="pending", text="Meus pedidos", customer_binding=str(customer.pk)
        )
        def model(messages, tools):
            if not any(row.get("role") == "tool" for row in messages):
                return {"tool_calls": [{"id": "order", "type": "function", "function": {"name": "get_own_order_status", "arguments": '{"order_id":4}'}}]}
            Customer.objects.filter(snapshot=self.snapshot, source_id=1).update(phone="")
            answer = {"outcome": "answer", "text": "Rastreio BRQM7890123BR", "reason": None}
            return {"content": json.dumps(answer)}
        sender = Mock(return_value="wamid.reply")
        process_next(model_client=model, send_client=sender)
        sent_texts = [call.args[0].text for call in sender.call_args_list]
        self.assertNotIn("BRQM7890123BR", " ".join(sent_texts))
        self.assertTrue(not sent_texts or sent_texts == [FAILURE_TEXT])
