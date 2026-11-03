"""Minimal Meta text-send client with injectable HTTP transport."""

from typing import Any

import httpx
from django.conf import settings


class MetaClient:
    """Send one persisted reply and return only Meta's acceptance message ID."""

    def __init__(
        self,
        *,
        base_url: str | None = None,
        token: str | None = None,
        business_id: str | None = None,
        phone_number_id: str | None = None,
        api_version: str | None = None,
        client: httpx.Client | None = None,
    ) -> None:
        """Configure the Meta endpoint, bearer token, scope IDs, and transport."""
        self.base_url = _configured(base_url, settings.META_BASE_URL).rstrip("/")
        self.token = _configured(token, settings.META_API_TOKEN)
        self.phone_number_id = _configured(phone_number_id, settings.META_PHONE_NUMBER_ID)
        self.api_version = _configured(api_version, settings.META_API_VERSION)
        self.client = client or httpx.Client(timeout=5.0)

    def __call__(self, reply: Any) -> str:
        """POST a supported text payload and validate its acceptance ID."""
        payload = self._payload(reply)
        response = self.client.post(
            f"{self.base_url}/{self.api_version}/{self.phone_number_id}/messages",
            headers={"Authorization": f"Bearer {self.token}"},
            json=payload,
            timeout=5.0,
        )
        response.raise_for_status()
        return _acceptance_id(response.json())

    def _payload(self, reply: Any) -> dict[str, Any]:
        source = reply.source
        context = {"message_id": source.provider_id}
        return {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": source.conversation.sender,
            "type": "text",
            "text": {"preview_url": False, "body": reply.text},
            "context": context,
        }


def _configured(value: str | None, fallback: str) -> str:
    return fallback if value is None else value


def _acceptance_id(body: Any) -> str:
    provider_id = _message_id(_first_message(body))
    if not isinstance(provider_id, str) or not provider_id:
        raise ValueError("Meta acceptance omitted message ID")
    return provider_id


def _first_message(body):
    messages = body.get("messages") if isinstance(body, dict) else None
    return messages[0] if isinstance(messages, list) and messages else None


def _message_id(message):
    return message.get("id") if isinstance(message, dict) else None
