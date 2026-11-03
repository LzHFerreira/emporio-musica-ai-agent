"""Authenticate, scope, minimize, and persist WhatsApp callbacks."""

import hashlib
import hmac
import json
import re
from datetime import UTC, datetime, timedelta
from typing import Any

from django.conf import settings
from django.db import DatabaseError, transaction
from django.utils import timezone as django_timezone

from emporio.catalog.models import SourceSnapshot
from emporio.chat.delivery import record_status
from emporio.chat.models import Conversation, IncomingMessage
from emporio.chat.privacy import minimize_text
from emporio.orders_access import sender_binding

MAX_BODY = 256 * 1024
MAX_ITEMS = 50
UNSUPPORTED_TEXT = "Posso ajudar apenas com mensagens de texto nesta conversa."


def signature_valid(raw: bytes, value: str | None) -> bool:
    """Compare the Meta raw-body HMAC without parsing or logging the body."""
    if not value or not value.startswith("sha256="):
        return False
    digest = hmac.new(settings.META_APP_SECRET.encode(), raw, hashlib.sha256).hexdigest()
    return hmac.compare_digest(value[7:], digest)


def process_envelope(raw: bytes) -> int:
    """Persist valid scoped messages and update delivery states from one envelope."""
    if len(raw) > MAX_BODY:
        raise ValueError("body_limit")
    payload = json.loads(raw)
    _valid_envelope(payload)
    count = _item_count(payload)
    if count > MAX_ITEMS:
        raise ValueError("batch_limit")
    return _process_entries(payload["entry"])


def _process_entries(entries) -> int:
    return sum(_process_entry(entry) for entry in entries if isinstance(entry, dict))


def _process_entry(entry) -> int:
    if entry.get("id") != settings.META_BUSINESS_ID:
        return 0
    return sum(
        _process_change(change) for change in entry.get("changes", []) if isinstance(change, dict)
    )


def _process_change(change) -> int:
    value = change.get("value", {})
    return _process_value(value) if isinstance(value, dict) and _phone_scope(value) else 0


def _valid_envelope(payload: Any) -> None:
    if not isinstance(payload, dict) or payload.get("object") != "whatsapp_business_account":
        raise ValueError("invalid_envelope")
    if not isinstance(payload.get("entry"), list):
        raise ValueError("invalid_envelope")


def _item_count(payload: dict[str, Any]) -> int:
    return sum(
        len(change.get("value", {}).get("messages", []))
        + len(change.get("value", {}).get("statuses", []))
        for entry in payload["entry"]
        if isinstance(entry, dict)
        for change in entry.get("changes", [])
        if isinstance(change, dict)
    )


def _phone_scope(value: dict[str, Any]) -> bool:
    metadata = value.get("metadata", {})
    return (
        value.get("messaging_product") == "whatsapp"
        and isinstance(metadata, dict)
        and metadata.get("phone_number_id") == settings.META_PHONE_NUMBER_ID
    )


def _process_value(value: dict[str, Any]) -> int:
    accepted = 0
    for message in value.get("messages", []):
        accepted += int(_persist_message(message))
    for status in value.get("statuses", []):
        record_status(status, settings.META_PHONE_NUMBER_ID)
    return accepted


def _persist_message(message: Any) -> bool:
    if not isinstance(message, dict):
        return False
    sender, provider_id = message.get("from"), message.get("id")
    if not _valid_identity(sender, provider_id):
        return False
    text, state = _minimized_text(message)
    now = django_timezone.now()
    occurred = _occurred(message.get("timestamp"), now)
    if occurred is None:
        return False
    fingerprint = hashlib.sha256(f"{sender}\0{text}".encode()).hexdigest()
    try:
        return _save_message(sender, provider_id, text, state, fingerprint, now, occurred, message)
    except DatabaseError:
        raise


def _save_message(sender, provider_id, text, state, fingerprint, now, occurred, message):
    with transaction.atomic():
        existing = IncomingMessage.objects.filter(provider_id=provider_id).first()
        if existing is not None:
            return False
        conversation, _ = Conversation.objects.get_or_create(sender=sender)
        if conversation.mode != "automation":
            state = "routed_to_operator"
        snapshot = SourceSnapshot.objects.filter(is_active=True).first()
        row = IncomingMessage.objects.create(
            conversation=conversation,
            provider_id=provider_id,
            sender=sender,
            fingerprint=fingerprint,
            text=text,
            state=state,
            received_at=now,
            occurred_at=occurred,
            deadline=now + timedelta(seconds=60),
            snapshot_version=snapshot.version if snapshot else "",
            customer_binding=sender_binding(sender, snapshot.version) if snapshot else "",
            reply_to_id=_reply_reference(message),
        )
        _advance_customer_time(conversation, occurred)
        return row.pk is not None


def _advance_customer_time(conversation, occurred):
    """Keep service-window evidence monotonic when delayed messages arrive."""
    if conversation.last_customer_at is None or occurred > conversation.last_customer_at:
        conversation.last_customer_at = occurred
        conversation.save(update_fields=["last_customer_at"])


def _valid_identity(sender, provider_id) -> bool:
    return (
        isinstance(sender, str)
        and re.fullmatch(r"[1-9][0-9]{7,14}", sender) is not None
        and isinstance(provider_id, str)
        and 1 <= len(provider_id) <= 200
    )


def _minimized_text(message) -> tuple[str, str]:
    if message.get("type") != "text" or not isinstance(message.get("text"), dict):
        return UNSUPPORTED_TEXT, "unsupported"
    cleaned = minimize_text(message["text"].get("body"))
    if cleaned is None:
        return UNSUPPORTED_TEXT, "unsupported"
    return cleaned, "pending"


def _occurred(timestamp, now):
    if not _valid_timestamp(timestamp):
        return None
    occurred = _parse_timestamp(timestamp)
    if occurred is None or (occurred - now).total_seconds() > 60:
        return None
    return min(occurred, now)


def _valid_timestamp(value) -> bool:
    return isinstance(value, str) and value.isascii() and value.isdigit()


def _parse_timestamp(timestamp):
    try:
        return datetime.fromtimestamp(int(timestamp), tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None


def _reply_reference(message):
    context = message.get("context")
    value = context.get("id") if isinstance(context, dict) else ""
    return value[:200] if isinstance(value, str) else ""
