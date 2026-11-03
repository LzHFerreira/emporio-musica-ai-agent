"""Repeatable local demo, queued-work, and source-failure behavior."""

import json
import re
from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TransactionTestCase
from django.utils import timezone

from emporio.agent_protocol import FAILURE_TEXT
from emporio.catalog.models import SourceSnapshot
from emporio.chat.demo_script import CASES, ScriptedModelClient
from emporio.chat.models import Conversation, IncomingMessage
from emporio.chat.worker import process_next
from tests.source_csv_fixtures import DATA_DIR


class DemoOperationalContractTests(TransactionTestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)
        self.snapshot = SourceSnapshot.objects.get(is_active=True)

    def test_repeated_runs_use_fresh_synthetic_ids_and_separate_send_counters(self):
        reports = self._two_run_reports()
        self._assert_report_counters(reports)
        self._assert_synthetic_ids(reports)

    def _two_run_reports(self):
        return [self._run_report() for _ in range(2)]

    def _assert_report_counters(self, reports):
        self.assertTrue(all(r["accepted_count"] == r["delivered_count"] == 5 for r in reports))

    def _assert_synthetic_ids(self, reports):
        messages = list(IncomingMessage.objects.order_by("pk"))
        ids = [item.provider_id for item in messages]
        self.assertEqual(len(ids), 10)
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(all(value.startswith("demo-in-") for value in ids))
        self.assertTrue(all(re.fullmatch(r"1555\d{9}", item.sender) for item in messages))
        self._assert_reports_hide_ids(reports, ids)

    def _assert_reports_hide_ids(self, reports, ids):
        for report in reports:
            encoded = json.dumps(report)
            self.assertTrue(all(provider_id not in encoded for provider_id in ids))

    def test_demo_fails_before_network_when_no_snapshot_or_unrelated_job_exists(self):
        SourceSnapshot.objects.update(is_active=False)
        with self.assertRaisesRegex(CommandError, "load canonical sources"):
            call_command("demo_chat", stdout=StringIO())
        SourceSnapshot.objects.update(is_active=True)
        self._pending_job()
        with self.assertRaisesRegex(CommandError, "idle worker queue"):
            call_command("demo_chat", stdout=StringIO())

    def test_public_policy_failure_emits_only_the_fixed_generic_reply(self):
        case = next(item for item in CASES if item["case"] == "policy_only")
        job = self._message(case["text"])
        unavailable = {"outcome": "error", "data": [], "sources": [], "error_category": "source_unavailable"}
        with patch("emporio.agent.lookup_public_policy", return_value=unavailable):
            reply = process_next(
                model_client=ScriptedModelClient(case), send_client=lambda _reply: "demo-accepted"
            )
        self.assertEqual(reply.text, FAILURE_TEXT)
        self.assertEqual(reply.state, "accepted")
        self.assertEqual(reply.source_id, job.pk)
        self.assertEqual(reply.source.sources, [])
        self.assertEqual(reply.source.operation_log[0]["outcome"], "error")

    def _run_report(self):
        output = StringIO()
        call_command("demo_chat", stdout=output)
        return json.loads(output.getvalue())

    def _pending_job(self):
        self._message("unrelated preexisting work", state="pending")

    def _message(self, text, state="pending"):
        now = timezone.now()
        sender = f"1555{IncomingMessage.objects.count() + 1:09d}"
        conversation = Conversation.objects.create(sender=sender, last_customer_at=now)
        return IncomingMessage.objects.create(
            conversation=conversation, provider_id=f"synthetic-{conversation.pk}", sender=sender,
            text=text, state=state, received_at=now, occurred_at=now,
            deadline=now.replace(year=now.year + 1), snapshot_version=self.snapshot.version,
        )
