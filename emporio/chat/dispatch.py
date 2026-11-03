"""Revalidate durable replies immediately before provider transmission."""

from collections.abc import Callable
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from emporio.agent_protocol import FAILURE_TEXT, HANDOFF_TEXT
from emporio.catalog.models import SourceSnapshot
from emporio.chat.lease import owns
from emporio.chat.models import OutgoingReply
from emporio.orders_access import sender_binding

SERVICE_WINDOW = timedelta(hours=24)


def dispatch(reply: OutgoingReply, send_client: Callable[[OutgoingReply], str]) -> OutgoingReply:
    """Send one reply after refreshing ownership, source, mode, and time gates."""
    if not owns():
        return reply
    _refresh(reply)
    return _dispatch_owned(reply, send_client)


def _dispatch_owned(reply: OutgoingReply, send_client: Callable[[OutgoingReply], str]):
    if _try_safe_fallback(reply):
        reply.text = FAILURE_TEXT
        reply.save(update_fields=["text"])
    block = _block_reason(reply)
    if block:
        return _defer(reply, block)
    return _send_after_checks(reply, send_client)


def _try_safe_fallback(reply):
    reason = _block_reason(reply)
    return reason in {"stale_source", "authorization_changed"} and _fallback_allowed(reply)


def _send_after_checks(reply: OutgoingReply, send_client: Callable[[OutgoingReply], str]):
    if _reserve_deadline_missed(reply.source):
        return _defer(reply, "deadline_expired")
    if not _mark_sending(reply):
        return reply
    return _record_acceptance(reply, _send(send_client, reply))


def _reserve_deadline_missed(job) -> bool:
    return not job.notification_only and job.deadline - timezone.now() < timedelta(seconds=5)


def _refresh(reply: OutgoingReply) -> None:
    reply.source.refresh_from_db()
    reply.source.conversation.refresh_from_db()


def _block_reason(reply: OutgoingReply) -> str | None:
    return _time_block(reply) or _conversation_block(reply) or _source_block(reply)


def _time_block(reply):
    job = reply.source
    if timezone.now() >= job.deadline and not job.notification_only:
        return "deadline_expired"
    return None if _window_open(job.conversation.last_customer_at) else "service_window_expired"


def _conversation_block(reply):
    conversation = reply.source.conversation
    if reply.text == HANDOFF_TEXT:
        return None if conversation.mode in {"human_pending", "human_active"} else "takeover"
    return None if conversation.mode == "automation" else "takeover"


def _source_block(reply):
    if not _requires_current_source(reply):
        return None
    if not _active_version_matches(reply.source.snapshot_version):
        return "stale_source"
    return None if _authorization_current(reply.source) else "authorization_changed"


def _requires_current_source(reply):
    job = reply.source
    return reply.text != FAILURE_TEXT and not job.notification_only and reply.text != HANDOFF_TEXT


def _active_version_matches(version):
    active = SourceSnapshot.objects.filter(is_active=True).first()
    return active is not None and active.version == version


def _authorization_current(job) -> bool:
    restricted = {"list_own_orders", "get_own_order_status"}
    if not any(
        item.get("tool") in restricted for item in job.operation_log if isinstance(item, dict)
    ):
        return True
    current = sender_binding(job.sender, job.snapshot_version)
    return bool(job.customer_binding) and current == job.customer_binding


def _window_open(last_customer_at) -> bool:
    return last_customer_at is not None and timezone.now() - last_customer_at <= SERVICE_WINDOW


def _fallback_allowed(reply: OutgoingReply) -> bool:
    return (
        owns()
        and reply.source.conversation.mode == "automation"
        and _window_open(reply.source.conversation.last_customer_at)
        and (timezone.now() < reply.source.deadline or reply.source.notification_only)
    )


def _defer(reply: OutgoingReply, reason: str) -> OutgoingReply:
    if reason == "takeover":
        reply.state = "blocked"
        reply.source.state = "routed_to_operator"
        reply.source.save(update_fields=["state"])
    else:
        reply.state = "notification_pending"
        reply.source.state = "notification_pending"
        reply.source.notification_only = True
        reply.source.save(update_fields=["state", "notification_only"])
    reply.failure_reason = reason
    reply.save(update_fields=["state", "failure_reason"])
    return reply


@transaction.atomic
def _mark_sending(reply: OutgoingReply) -> bool:
    _refresh(reply)
    if not owns() or _block_reason(reply) is not None:
        return False
    reply.state = "sending"
    reply.send_started_at = timezone.now()
    reply.save(update_fields=["state", "send_started_at"])
    return True


def _send(send_client: Callable[[OutgoingReply], str], reply: OutgoingReply) -> str | None:
    try:
        value = send_client(reply)
    except Exception:
        return None
    return value if isinstance(value, str) and value else None


@transaction.atomic
def _record_acceptance(reply: OutgoingReply, provider_id: str | None) -> OutgoingReply:
    reply.refresh_from_db()
    if not owns():
        return _record_unknown(reply, provider_id)
    return _record_known(reply, provider_id)


def _record_unknown(reply, provider_id):
    reply.state = "unknown"
    reply.provider_id = provider_id or ""
    reply.save(update_fields=["state", "provider_id"])
    return reply


def _record_known(reply, provider_id):
    reply.state = "accepted" if provider_id else "unknown"
    reply.provider_id = provider_id or ""
    reply.save(update_fields=["state", "provider_id"])
    if provider_id:
        from emporio.chat.delivery import reconcile_reply

        reconcile_reply(reply, settings.META_PHONE_NUMBER_ID)
        reply.refresh_from_db()
    return reply
