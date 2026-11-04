import json
import hashlib
import hmac
from datetime import datetime, timedelta, timezone as utc
from pathlib import Path
from unittest.mock import Mock, patch

import httpx
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from emporio.chat.meta import MetaClient
from emporio.chat.models import Conversation, IncomingMessage, OutgoingReply
from emporio.chat.cloudflare import CloudflareClient
from emporio.chat.worker import process_next

FIXTURES = Path(__file__).resolve().parents[1] / "docs/fixtures/meta-v24"


FACTS = ["catalog-1"]
DELIVERED = ("Para devolução, confirme as condições aplicáveis com a loja.\n"
             "Takamine GD20 Dreadnought Natural: disponível em estoque; R$ 2.199,00 "
             "(preço registrado; forma de pagamento não informada).")


def _gemma_callback_answers(final):
    lookup_calls = [
        {"id": "catalog", "type": "function", "function": {"name": "search_catalog", "arguments": '{"query":"Takamine GD20","mode":"resolve"}'}},
        {"id": "policy", "type": "function", "function": {"name": "lookup_public_policy", "arguments": '{"query":"devolução","topic":"returns"}'}},
    ]
    control = {"id": "reply", "type": "function", "function": {"name": "respond_to_customer", "arguments": json.dumps({"outcome": "answer", "text": final, "reason": None, "facts": FACTS}, ensure_ascii=False)}}
    terminal = {"outcome": "answer", "text": final, "reason": None, "facts": FACTS}
    return [_gemma_answer({"tool_calls": lookup_calls}, "tool_calls"), _gemma_answer({"tool_calls": [control]}, "tool_calls"), _gemma_answer({"content": json.dumps(terminal, ensure_ascii=False)}, "stop")]


def _gemma_answer(message, finish_reason):
    return {"choices": [{"message": {"role": "assistant", **message}, "finish_reason": finish_reason}], "model": "@cf/google/gemma-4-26b-a4b-it"}


class MetaClientContractTests(TestCase):
    def test_sends_fixture_wire_shape_and_returns_acceptance_id_only(self):
        conversation = Conversation.objects.create(sender="5567998123456", mode="automation")
        now = timezone.now()
        source = IncomingMessage.objects.create(
            conversation=conversation, provider_id="wamid.synthetic.incoming.1", sender="5567998123456",
            text="Qual o horário?", state="completed", received_at=now,
            occurred_at=now, deadline=now + timedelta(seconds=60), snapshot_version="snapshot-a",
        )
        reply = OutgoingReply.objects.create(source=source, text="O horário regular é de segunda a sexta, das 9h às 18h, e sábado, das 9h às 13h.", state="sending")
        expected = json.loads((FIXTURES / "outgoing-request.json").read_text())
        accepted = json.loads((FIXTURES / "acceptance-response.json").read_text())

        def respond(request):
            self.assertEqual(request.url, "https://meta.test/v24.0/100000000000002/messages")
            self.assertEqual(request.headers["Authorization"], "Bearer local-test-token")
            self.assertEqual(json.loads(request.content), expected)
            return httpx.Response(200, json=accepted)

        client = httpx.Client(transport=httpx.MockTransport(respond))
        sender = MetaClient(base_url="https://meta.test", token="local-test-token", business_id="100000000000001", phone_number_id="100000000000002", client=client)
        self.assertEqual(sender(reply), "wamid.synthetic.outgoing.1")
        client.close()

    def test_http_rejection_and_malformed_acceptance_id_fail_without_retry(self):
        conversation = Conversation.objects.create(sender="5567998123456")
        now = timezone.now()
        source = IncomingMessage.objects.create(conversation=conversation, provider_id="wamid.meta.fail", sender=conversation.sender, text="x", state="completed", received_at=now, occurred_at=now, deadline=now + timedelta(seconds=60))
        reply = OutgoingReply.objects.create(source=source, text="reply", state="sending")
        seen = []
        def reject(request):
            seen.append(request)
            return httpx.Response(429, json={"error": {"code": 130429}})
        client = httpx.Client(transport=httpx.MockTransport(reject))
        sender = MetaClient(base_url="https://meta.test", token="local-test-token", phone_number_id="100000000000002", client=client)
        with self.assertRaises(httpx.HTTPStatusError):
            sender(reply)
        self.assertEqual(len(seen), 1)
        client.close()

    def test_http_success_without_provider_message_id_is_not_acceptance(self):
        conversation = Conversation.objects.create(sender="5567998123456")
        now = timezone.now()
        source = IncomingMessage.objects.create(conversation=conversation, provider_id="wamid.meta.malformed", sender=conversation.sender, text="x", state="completed", received_at=now, occurred_at=now, deadline=now + timedelta(seconds=60))
        reply = OutgoingReply.objects.create(source=source, text="reply", state="sending")
        client = httpx.Client(transport=httpx.MockTransport(lambda request: httpx.Response(200, json={"messages": [{}]})))
        sender = MetaClient(base_url="https://meta.test", token="local-test-token", phone_number_id="100000000000002", client=client)
        with self.assertRaises(ValueError):
            sender(reply)
        client.close()


@override_settings(META_BASE_URL="https://meta.test", META_API_TOKEN="local-test-token", META_PHONE_NUMBER_ID="100000000000002", META_APP_SECRET="test-secret", META_BUSINESS_ID="100000000000001")
class CustomerTurnIntegrationTests(TestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(Path(__file__).resolve().parents[1] / "data"), verbosity=0)

    def signed_job(self):
        incoming = json.loads((FIXTURES / "incoming-text.json").read_text())
        event = incoming["entry"][0]["changes"][0]["value"]["messages"][0]
        happened = datetime.fromtimestamp(int(event["timestamp"]), tz=utc.utc)
        event["text"]["body"] = "O Takamine GD20 está disponível e posso devolver?"
        raw = json.dumps(incoming).encode()
        signature = hmac.new(b"test-secret", raw, hashlib.sha256).hexdigest()
        with patch("django.utils.timezone.now", return_value=happened):
            ingress = Client().post("/webhooks/whatsapp", data=raw, content_type="application/json", HTTP_X_HUB_SIGNATURE_256=f"sha256={signature}")
        self.assertEqual((ingress.status_code, ingress.content), (200, b""))
        return IncomingMessage.objects.get(), happened

    def model(self, job):
        calls = [
            {"id": "catalog", "type": "function", "function": {"name": "search_catalog", "arguments": '{"query":"Takamine GD20","mode":"resolve"}'}},
            {"id": "policy", "type": "function", "function": {"name": "lookup_public_policy", "arguments": '{"query":"devolução","topic":"returns"}'}},
        ]
        final = "Para devolução, confirme as condições aplicáveis com a loja."
        model = Mock(side_effect=[{"tool_calls": calls}, {"content": json.dumps({"outcome": "answer", "text": final, "reason": None, "facts": FACTS})}])
        seen_counts = []

        def counted_model(messages, tools):
            job.refresh_from_db()
            seen_counts.append(job.model_requests)
            return model(messages, tools)

        return final, seen_counts, model, counted_model

    def meta_sender(self, final):
        expected = json.loads((FIXTURES / "outgoing-request.json").read_text())
        expected["text"]["body"] = final
        accepted = json.loads((FIXTURES / "acceptance-response.json").read_text())

        def respond(request):
            self.assertEqual(request.url.path, "/v24.0/100000000000002/messages")
            self.assertEqual(json.loads(request.content), expected)
            return httpx.Response(200, json=accepted)

        meta_http = httpx.Client(transport=httpx.MockTransport(respond))
        sender = MetaClient(base_url="https://meta.test", token="local-test-token", phone_number_id="100000000000002", client=meta_http)
        return sender, meta_http

    def test_real_catalog_policy_worker_and_meta_client_complete_one_signed_fixture_turn(self):
        job, happened = self.signed_job()
        final, seen_counts, model, counted_model = self.model(job)
        sender, meta_http = self.meta_sender(DELIVERED)
        with patch("django.utils.timezone.now", return_value=happened + timedelta(seconds=1)):
            reply = process_next(model_client=counted_model, send_client=sender)
        meta_http.close()
        job.refresh_from_db()
        self.assert_reply_completion(reply, model)
        self.assert_model_usage(job, seen_counts)
        self.assert_evidence_is_minimized(job)

    def test_gemma_reply_control_finishes_after_catalog_and_policy_results(self):
        job, happened = self.signed_job()
        final = "Para devolução, confirme as condições aplicáveis com a loja."
        cloud_requests = []
        answers = iter(_gemma_callback_answers(final))

        def respond(request):
            cloud_requests.append(json.loads(request.content))
            return httpx.Response(200, json=next(answers))

        cloud_http = httpx.Client(transport=httpx.MockTransport(respond))
        model = CloudflareClient(account_id="acct", api_key="cf-key", model="@cf/google/gemma-4-26b-a4b-it", client=cloud_http)
        sender, meta_http = self.meta_sender(DELIVERED)
        with patch("django.utils.timezone.now", return_value=happened + timedelta(seconds=1)):
            reply = process_next(model_client=model, send_client=sender)
        cloud_http.close()
        meta_http.close()
        job.refresh_from_db()
        self.assertEqual((reply.state, reply.provider_id, reply.text), ("accepted", "wamid.synthetic.outgoing.1", DELIVERED))
        self.assertEqual((len(cloud_requests), job.model_requests, job.tool_executions), (2, 2, 2))
        replay = cloud_requests[1]["messages"]
        tool_results = [message for message in replay if message["role"] == "tool"]
        self.assertEqual([message["tool_call_id"] for message in tool_results], ["catalog", "policy"])
        self.assertIn("Takamine GD20", tool_results[0]["content"])
        self.assertIn("devolução", tool_results[1]["content"])

    def assert_reply_completion(self, reply, model):
        self.assertEqual((reply.state, reply.provider_id), ("accepted", "wamid.synthetic.outgoing.1"))
        self.assertEqual(model.call_count, 2)

    def assert_model_usage(self, job, seen_counts):
        self.assertEqual((seen_counts, job.model_requests, job.tool_executions), ([1, 2], 2, 2))

    def assert_evidence_is_minimized(self, job):
        from emporio.orders.models import Customer
        customer = Customer.objects.get(snapshot__version=job.snapshot_version, source_id=1)
        self.assertEqual(job.customer_binding, str(customer.pk))
        self.assertEqual(job.prompt_version, "store-assistant-v1")
        self.assert_operation_log(job)
        self.assert_source_locators(job)

    def assert_operation_log(self, job):
        self.assertEqual({row["outcome"] for row in job.operation_log}, {"found"})
        self.assertTrue(all(set(row) == {"tool", "outcome"} for row in job.operation_log))

    def assert_source_locators(self, job):
        self.assertEqual({item["type"] for item in job.sources}, {"catalog", "policy"})
        self.assertTrue(all(set(item) == {"type", "label", "page", "section", "bundle_version"} for item in job.sources))
        self.assertTrue(all(item["bundle_version"] == job.snapshot_version for item in job.sources))
        self.assertNotIn("Takamine GD20 Dreadnought Natural", json.dumps(job.sources))
