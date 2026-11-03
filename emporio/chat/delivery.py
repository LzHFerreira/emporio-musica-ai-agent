"""Apply monotonic, recipient-scoped Meta delivery callbacks."""

import re
from datetime import UTC, datetime, timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone as django_timezone

from emporio.chat.models import DeliveryEvent, OutgoingReply

STATES = {"sent", "delivered", "read", "failed"}
RANK = {"accepted": 0, "sent": 1, "delivered": 2, "read": 3}


@transaction.atomic
def record_status(status, phone_number_id: str) -> None:
    """Apply a known callback or retain a bounded early status for reconciliation."""
    values = _status_values(status)
    if values is None or phone_number_id != settings.META_PHONE_NUMBER_ID:
        return
    _attach_or_retain(values, phone_number_id)


def _attach_or_retain(values, phone_number_id):
    provider_id, recipient, state, occurred = values
    reply = (
        OutgoingReply.objects.filter(provider_id=provider_id)
        .select_related("source__conversation")
        .first()
    )
    if reply and reply.source.conversation.sender == recipient:
        _apply(reply, state, occurred)
        return
    if reply:
        return
    _retain(provider_id, recipient, state, occurred, phone_number_id)


@transaction.atomic
def reconcile_reply(reply: OutgoingReply, phone_number_id: str) -> None:
    """Attach only early statuses matching the accepted ID and recipient."""
    events = DeliveryEvent.objects.filter(
        phone_number_id=phone_number_id,
        provider_id=reply.provider_id,
        recipient_id=reply.source.conversation.sender,
    ).order_by("occurred_at", "pk")
    for event in events:
        _apply(reply, event.status, event.occurred_at)
        event.delete()


def _status_values(status):
    if not _status_shape(status):
        return None
    fields = _status_fields(status)
    if fields is None:
        return None
    recipient, state, raw_time = fields
    occurred = _parse_time(raw_time)
    return (status["id"], recipient, state, occurred) if occurred else None


def _status_fields(status):
    recipient, state, raw_time = (
        status.get("recipient_id"),
        status.get("status"),
        status.get("timestamp"),
    )
    if _valid_recipient(recipient) and _valid_state(state) and _valid_time(raw_time):
        return recipient, state, raw_time
    return None


def _status_shape(status):
    return isinstance(status, dict) and isinstance(status.get("id"), str) and bool(status["id"])


def _valid_recipient(value):
    return isinstance(value, str) and re.fullmatch(r"[1-9][0-9]{7,14}", value) is not None


def _valid_state(value):
    return isinstance(value, str) and value in STATES


def _valid_time(value):
    return isinstance(value, str) and value.isascii() and value.isdigit()


def _parse_time(raw_time):
    try:
        occurred = datetime.fromtimestamp(int(raw_time), tz=UTC)
    except (OverflowError, OSError, ValueError):
        return None
    if (occurred - django_timezone.now()).total_seconds() > 60:
        return None
    return min(occurred, django_timezone.now())


def _retain(provider_id, recipient, state, occurred, phone_number_id):
    now = django_timezone.now()
    DeliveryEvent.objects.filter(received_at__lt=now - timedelta(hours=24)).delete()
    key = {
        "phone_number_id": phone_number_id,
        "provider_id": provider_id,
        "recipient_id": recipient,
        "status": state,
        "occurred_at": occurred,
    }
    if DeliveryEvent.objects.filter(**key).exists():
        return
    if DeliveryEvent.objects.count() >= 1000:
        raise OverflowError("unmatched status capacity reached")
    DeliveryEvent.objects.create(**key)


def _apply(reply, state, occurred):
    if state == "failed":
        _apply_failure(reply)
    elif _progress_is_new(reply, state, occurred):
        reply.state = state
    else:
        return
    reply.delivery_at = occurred
    reply.save(update_fields=["state", "delivery_at"])


def _apply_failure(reply):
    if reply.state not in {"delivered", "read"}:
        reply.state = "failed"


def _progress_is_new(reply, state, occurred):
    return RANK.get(state, -1) > RANK.get(reply.state, -1) and (
        reply.delivery_at is None or occurred >= reply.delivery_at
    )
