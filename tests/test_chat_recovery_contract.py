from datetime import timedelta
from unittest.mock import Mock

from django.test import TestCase
from django.utils import timezone

from emporio.chat.models import Conversation, IncomingMessage, OutgoingReply
from emporio.chat.recovery import recover_interrupted
from emporio.chat.worker import process_next


class WorkerRecoveryContractTests(TestCase):
    def make_message(self, state):
        conversation = Conversation.objects.create(sender="opaque-sender", mode="automation")
        now = timezone.now()
        return IncomingMessage.objects.create(
            conversation=conversation, provider_id="wamid.synthetic.restart", sender="opaque-sender",
            text="Qual o horário?", state=state, received_at=now,
            occurred_at=now, deadline=now + timedelta(seconds=60), snapshot_version="snapshot-a",
        )

    def test_running_work_is_interrupted_and_uncertain_send_is_never_replayed(self):
        job = self.make_message("running")
        reply = OutgoingReply.objects.create(source=job, text="draft", state="sending")
        recover_interrupted()
        model, send = Mock(), Mock()
        self.assertIsNone(process_next(model_client=model, send_client=send))
        job.refresh_from_db()
        reply.refresh_from_db()
        self.assertEqual((job.state, reply.state), ("interrupted", "unknown"))
        model.assert_not_called()
        send.assert_not_called()

    def test_unclaimed_pending_job_keeps_original_deadline_and_snapshot(self):
        job = self.make_message("pending")
        original_deadline = job.deadline
        recover_interrupted()
        job.refresh_from_db()
        self.assertEqual((job.state, job.deadline, job.snapshot_version), ("pending", original_deadline, "snapshot-a"))

    def test_accepted_reply_waits_for_callback_without_another_send(self):
        job = self.make_message("completed")
        reply = OutgoingReply.objects.create(source=job, text="answer", state="accepted", provider_id="wamid.synthetic.outgoing")
        send = Mock()
        self.assertIsNone(process_next(model_client=Mock(), send_client=send))
        reply.refresh_from_db()
        self.assertEqual(reply.state, "accepted")
        send.assert_not_called()
