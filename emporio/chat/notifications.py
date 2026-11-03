"""Persist one fixed notice for an expired customer response window."""

from django.db import transaction
from django.utils import timezone

from emporio.agent_protocol import FAILURE_TEXT
from emporio.chat.models import IncomingMessage, OutgoingReply


@transaction.atomic
def prepare_expired_notice() -> OutgoingReply | None:
    """Record an operator-visible notice without sending it in the same pass."""
    job = (
        IncomingMessage.objects.filter(state="pending", deadline__lte=timezone.now())
        .select_related("conversation")
        .order_by("received_at", "pk")
        .first()
    )
    if job is None:
        return None
    if job.conversation.mode != "automation":
        job.state = "routed_to_operator"
        job.save(update_fields=["state"])
        return None
    job.state = "notification_pending"
    job.notification_only = True
    job.save(update_fields=["state", "notification_only"])
    reply, _ = OutgoingReply.objects.get_or_create(
        source=job,
        defaults={"text": FAILURE_TEXT, "state": "notification_pending"},
    )
    return reply
