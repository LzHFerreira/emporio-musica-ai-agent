import httpx
from django.test import SimpleTestCase

from emporio.chat.demo_http import MetaAcceptanceServer


class MetaAcceptanceMockContractTests(SimpleTestCase):
    def test_mock_validates_endpoint_credentials_and_supported_text_payload(self):
        payload = {"messaging_product": "whatsapp", "recipient_type": "individual", "to": "5567998123456", "type": "text", "text": {"preview_url": False, "body": "Oi"}, "context": {"message_id": "wamid.in"}}
        with MetaAcceptanceServer() as server, httpx.Client() as client:
            path = "/v24.0/100000000000002/messages"
            headers = {"Authorization": "Bearer local-demo-only"}
            valid = client.post(server.base_url + path, headers=headers, json=payload)
            wrong_path = client.post(server.base_url + "/wrong", headers=headers, json=payload)
            wrong_auth = client.post(server.base_url + path, headers={"Authorization": "Bearer wrong"}, json=payload)
            malformed = client.post(server.base_url + path, headers=headers, json={"messaging_product": "whatsapp"})
        self.assertEqual((valid.status_code, wrong_path.status_code, wrong_auth.status_code, malformed.status_code), (200, 404, 401, 400))
        self.assertEqual(len(server.accepted), 1)
