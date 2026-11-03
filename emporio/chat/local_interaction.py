"""Run evaluator-entered turns through the signed local chat boundary."""

from itertools import chain
from time import time
from uuid import uuid4

from django.conf import settings
from django.core.management.base import CommandError

from emporio.catalog.models import SourceSnapshot
from emporio.chat.demo_http import MetaAcceptanceServer, signed_post, webhook_server
from emporio.chat.meta import MetaClient
from emporio.chat.models import IncomingMessage, OutgoingReply
from emporio.chat.worker import process_next


def run_interaction(messages, model_client, stdout):
    """Submit each evaluator message and print its worker-validated reply."""
    if SourceSnapshot.objects.filter(is_active=True).first() is None:
        raise CommandError("Load canonical sources before starting interact_chat")
    iterator = iter(messages)
    first = next(iterator, None)
    if first is None:
        return
    _require_idle_worker()
    sender = _synthetic_sender()
    with MetaAcceptanceServer() as provider, webhook_server() as webhook:
        sender_client = MetaClient(base_url=provider.base_url, token="local-demo-only")
        try:
            for index, message in enumerate(chain((first,), iterator), start=1):
                reply = _run_one(
                    webhook, provider.run_id, sender, index, message, model_client, sender_client
                )
                stdout.write(reply.text)
        finally:
            sender_client.client.close()


def _run_one(webhook, run_id, sender, index, text, model_client, sender_client):
    provider_id = f"interact-{run_id}-{index}"
    status = _post_message(webhook, provider_id, sender, text)
    if status != 200:
        raise CommandError(f"Local webhook returned HTTP {status}")
    reply = process_next(model_client=model_client, send_client=sender_client)
    if reply is None or reply.state != "accepted":
        raise CommandError("The local turn did not reach mock Meta acceptance")
    if reply.source.provider_id != provider_id:
        raise CommandError("The local worker processed a different message")
    return reply


def _post_message(webhook, provider_id, sender, text):
    message = {
        "from": sender,
        "id": provider_id,
        "timestamp": str(int(time())),
        "type": "text",
        "text": {"body": text},
    }
    return signed_post(webhook, _webhook_envelope(message), settings.META_APP_SECRET)


def _webhook_envelope(message):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": settings.META_BUSINESS_ID,
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": settings.META_PHONE_NUMBER_ID},
                            "messages": [message],
                        }
                    }
                ],
            }
        ],
    }


def _synthetic_sender():
    return "1555" + str(int(uuid4().hex[:9], 16)).zfill(10)


def _require_idle_worker():
    active = ("pending", "unsupported", "notification_pending", "running")
    if (
        IncomingMessage.objects.filter(state__in=active).exists()
        or OutgoingReply.objects.filter(state__in=("queued", "notification_pending")).exists()
    ):
        raise CommandError("Process existing work before starting interact_chat")
