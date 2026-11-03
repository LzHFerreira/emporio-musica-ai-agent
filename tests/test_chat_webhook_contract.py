import hashlib
import hmac
import json
from pathlib import Path
from unittest.mock import patch

from django.db import DatabaseError
from django.test import Client, TestCase, override_settings

from django.utils import timezone

from emporio.chat.models import Conversation, IncomingMessage

FIXTURES = Path(__file__).resolve().parents[1] / "docs/fixtures/meta-v24"


class WebhookTestSupport:
    def setUp(self):
        self.client = Client()

    def post_fixture(self, name, *, signature=True):
        body = (FIXTURES / name).read_bytes()
        return self.post_body(body, signature=signature)

    def post_body(self, body, *, signature=True):
        digest = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
        headers = {"HTTP_X_HUB_SIGNATURE_256": f"sha256={digest}"} if signature else {}
        return self.client.post("/webhooks/whatsapp", data=body, content_type="application/json", **headers)

@override_settings(META_APP_SECRET="test-secret", META_WEBHOOK_VERIFY_TOKEN="verify-me", META_BUSINESS_ID="100000000000001", META_PHONE_NUMBER_ID="100000000000002")
class WebhookIngressContractTests(WebhookTestSupport, TestCase):
    def test_get_verification_returns_only_exact_challenge_for_valid_token(self):
        valid = self.client.get("/webhooks/whatsapp", {"hub.mode": "subscribe", "hub.verify_token": "verify-me", "hub.challenge": "challenge-123"})
        invalid = self.client.get("/webhooks/whatsapp", {"hub.mode": "subscribe", "hub.verify_token": "wrong", "hub.challenge": "challenge-123"})
        self.assertEqual((valid.status_code, valid.content, invalid.status_code), (200, b"challenge-123", 403))

    def test_missing_verification_fields_invalid_http_method_and_malformed_envelope(self):
        self.assertEqual(self.client.get("/webhooks/whatsapp").status_code, 400)
        self.assertEqual(self.client.delete("/webhooks/whatsapp").status_code, 405)
        malformed = b"not-json"
        digest = hmac.new(b"test-secret", malformed, hashlib.sha256).hexdigest()
        response = self.client.post("/webhooks/whatsapp", data=malformed, content_type="application/json", HTTP_X_HUB_SIGNATURE_256=f"sha256={digest}")
        self.assertEqual(response.status_code, 400)

    def test_body_and_batch_limits_fail_before_creating_jobs(self):
        oversized = b"x" * (256 * 1024 + 1)
        self.assertEqual(self.post_body(oversized).status_code, 413)
        payload = json.loads((FIXTURES / "incoming-text.json").read_bytes())
        messages = payload["entry"][0]["changes"][0]["value"]["messages"]
        messages.extend(json.loads(json.dumps(messages[0])) for _ in range(50))
        self.assertEqual(self.post_body(json.dumps(payload).encode()).status_code, 413)
        self.assertEqual(IncomingMessage.objects.count(), 0)

    def test_persistence_failure_is_not_acknowledged(self):
        body = (FIXTURES / "incoming-text.json").read_bytes()
        digest = hmac.new(b"test-secret", body, hashlib.sha256).hexdigest()
        with patch("emporio.chat.views.process_envelope", side_effect=DatabaseError("locked")):
            response = self.client.post("/webhooks/whatsapp", data=body, content_type="application/json", HTTP_X_HUB_SIGNATURE_256=f"sha256={digest}")
        self.assertEqual(response.status_code, 503)

    def test_raw_signature_required_before_persisting_incoming_work(self):
        rejected = self.post_fixture("incoming-text.json", signature=False)
        self.assertEqual((rejected.status_code, IncomingMessage.objects.count()), (403, 0))
        accepted = self.post_fixture("incoming-text.json")
        self.assertEqual((accepted.status_code, accepted.content, IncomingMessage.objects.count()), (200, b"", 1))

    def test_duplicate_message_and_status_callback_create_no_extra_agent_work(self):
        self.post_fixture("incoming-text.json")
        duplicate = self.post_fixture("incoming-text.json")
        before_status = IncomingMessage.objects.count()
        callback = self.post_fixture("delivery-callback.json")
        self.assertEqual((duplicate.status_code, callback.status_code), (200, 200))
        self.assertEqual(IncomingMessage.objects.count(), before_status)

    def test_signature_uses_raw_bytes_not_reformatted_json(self):
        body = (FIXTURES / "incoming-text.json").read_bytes()
        compact = json.dumps(json.loads(body), separators=(",", ":")).encode()
        digest = hmac.new(b"test-secret", compact, hashlib.sha256).hexdigest()
        response = self.client.post("/webhooks/whatsapp", data=body, content_type="application/json", HTTP_X_HUB_SIGNATURE_256=f"sha256={digest}")
        self.assertEqual(response.status_code, 403)

@override_settings(META_APP_SECRET="test-secret", META_WEBHOOK_VERIFY_TOKEN="verify-me", META_BUSINESS_ID="100000000000001", META_PHONE_NUMBER_ID="100000000000002")
class WebhookMessageContractTests(WebhookTestSupport, TestCase):
    def test_batch_walks_multiple_entries_and_changes(self):
        payload = json.loads((FIXTURES / "incoming-text.json").read_bytes())
        second = json.loads(json.dumps(payload["entry"][0]["changes"][0]))
        second["value"]["messages"][0]["id"] = "wamid.synthetic.incoming.2"
        payload["entry"].append({"id": "100000000000001", "changes": [second]})
        response = self.post_body(json.dumps(payload).encode())
        self.assertEqual((response.status_code, IncomingMessage.objects.count()), (200, 2))

    def test_wrong_phone_scope_is_acknowledged_without_creating_work(self):
        payload = json.loads((FIXTURES / "incoming-text.json").read_bytes())
        payload["entry"][0]["changes"][0]["value"]["metadata"]["phone_number_id"] = "other-phone"
        response = self.post_body(json.dumps(payload).encode())
        self.assertEqual((response.status_code, IncomingMessage.objects.count()), (200, 0))

    def test_wrong_business_and_messaging_product_are_ignored(self):
        payload = json.loads((FIXTURES / "incoming-text.json").read_bytes())
        payload["entry"][0]["id"] = "other-business"
        self.assertEqual(self.post_body(json.dumps(payload).encode()).status_code, 200)
        payload["entry"][0]["id"] = "100000000000001"
        payload["entry"][0]["changes"][0]["value"]["messaging_product"] = "other-channel"
        self.assertEqual(self.post_body(json.dumps(payload).encode()).status_code, 200)
        self.assertEqual(IncomingMessage.objects.count(), 0)

    def test_provider_id_reused_with_conflicting_content_does_not_create_work(self):
        self.post_fixture("incoming-text.json")
        payload = json.loads((FIXTURES / "incoming-text.json").read_bytes())
        payload["entry"][0]["changes"][0]["value"]["messages"][0]["text"]["body"] = "different content"
        response = self.post_body(json.dumps(payload).encode())
        self.assertEqual((response.status_code, IncomingMessage.objects.count()), (200, 1))

    def test_paused_conversation_routes_new_message_without_agent_job(self):
        Conversation.objects.create(sender="5567998123456", mode="human_pending")
        response = self.post_fixture("incoming-text.json")
        message = IncomingMessage.objects.get()
        self.assertEqual((response.status_code, message.state), (200, "routed_to_operator"))

    def test_malformed_sibling_does_not_discard_valid_batch_message(self):
        payload = json.loads((FIXTURES / "incoming-text.json").read_bytes())
        payload["entry"][0]["changes"][0]["value"]["messages"].insert(0, {"type": "text"})
        response = self.post_body(json.dumps(payload).encode())
        self.assertEqual((response.status_code, IncomingMessage.objects.count()), (200, 1))

    def test_contact_minimization_preserves_order_budget_and_model_code(self):
        payload = json.loads((FIXTURES / "incoming-text.json").read_bytes())
        message = payload["entry"][0]["changes"][0]["value"]["messages"][0]
        message["text"]["body"] = "Pedido 7, R$ 1.000, modelo AC-39; ana@example.com +55 67 99812-3456"
        self.post_body(json.dumps(payload).encode())
        stored = IncomingMessage.objects.get().text
        self.assertNotIn("ana@example.com", stored)
        self.assertNotIn("99812-3456", stored)
        self.assertIn("Pedido 7", stored)
        self.assertIn("R$ 1.000", stored)
        self.assertIn("AC-39", stored)

    def test_unsupported_media_is_persisted_as_fixed_notice_without_raw_payload(self):
        payload = json.loads((FIXTURES / "incoming-text.json").read_bytes())
        message = payload["entry"][0]["changes"][0]["value"]["messages"][0]
        message["type"] = "image"
        message.pop("text")
        message["image"] = {"caption": "secret contact maria@example.com", "id": "media-secret"}
        self.post_body(json.dumps(payload).encode())
        message = IncomingMessage.objects.get()
        self.assertEqual((message.state, message.text), ("unsupported", "Posso ajudar apenas com mensagens de texto nesta conversa."))
        self.assertNotIn("maria@example.com", message.text)
        self.assertNotIn("media-secret", message.text)
