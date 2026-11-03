"""Claim and run one durable job under the singleton process lease."""

from collections.abc import Callable
from datetime import timedelta
from threading import Event, Thread
from typing import Any, NotRequired, TypedDict

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from emporio.agent import run_turn
from emporio.agent_protocol import FAILURE_TEXT, HANDOFF_TEXT
from emporio.catalog.models import SourceSnapshot
from emporio.chat.context import conversation_history
from emporio.chat.dispatch import dispatch
from emporio.chat.lease import GENERATION, acquire, heartbeat, owns
from emporio.chat.model_tracking import TrackedModelClient
from emporio.chat.models import IncomingMessage, OutgoingReply
from emporio.chat.notifications import prepare_expired_notice
from emporio.chat.privacy import minimize_text
from emporio.chat.source_projection import safe_sources
from emporio.chat.webhook import UNSUPPORTED_TEXT

SERVICE_WINDOW = timedelta(hours=24)
ModelClient = Callable[[list[dict[str, Any]], list[dict[str, Any]]], dict[str, Any]]
SendClient = Callable[[OutgoingReply], str]


class _TurnArguments(TypedDict):
    sender: str
    model_client: ModelClient
    snapshot_version: str
    history: NotRequired[list[dict[str, str]]]


def process_next(*, model_client: ModelClient, send_client: SendClient) -> OutgoingReply | None:
    """Claim one oldest job, check budgets, and persist before sending."""
    if not acquire():
        return None
    return _run_under_lease(model_client, send_client)


def _run_under_lease(model_client: ModelClient, send_client: SendClient) -> OutgoingReply | None:
    stop = Event()
    thread = Thread(target=heartbeat, args=(stop,), daemon=True)
    thread.start()
    try:
        return _work_once(model_client, send_client)
    finally:
        stop.set()
        thread.join(timeout=2)


def _work_once(model_client: ModelClient, send_client: SendClient) -> OutgoingReply | None:
    queued = _resume_or_notice(send_client)
    if queued is not None:
        return queued
    job = _claim()
    if job is None or not owns():
        return None
    text, operations, sources = _draft(job, model_client)
    reply = _prepare_reply(job, text, operations, sources)
    return dispatch(reply, send_client) if reply is not None else None


def _resume_or_notice(send_client: SendClient) -> OutgoingReply | None:
    queued = _resume_queued()
    if queued is not None:
        return dispatch(queued, send_client)
    return prepare_expired_notice()


def _claim():
    now = timezone.now()
    unavailable = IncomingMessage.objects.filter(
        state__in=("pending", "unsupported", "notification_pending")
    )
    unavailable.exclude(conversation__mode="automation").update(state="routed_to_operator")
    available = (
        Q(state="pending", deadline__gt=now)
        | Q(state="unsupported")
        | Q(state="notification_pending", conversation__last_customer_at__gte=now - SERVICE_WINDOW)
    )
    with transaction.atomic():
        job = IncomingMessage.objects.filter(available).order_by("received_at", "pk").first()
        if job is None:
            return None
        changed = IncomingMessage.objects.filter(pk=job.pk, state=job.state).update(
            state="running", worker_generation=GENERATION
        )
        return IncomingMessage.objects.get(pk=job.pk) if changed else None


def _draft(
    job: IncomingMessage, model_client: ModelClient
) -> tuple[str, list[dict[str, Any]], list[dict[str, Any]]]:
    if job.notification_only:
        return FAILURE_TEXT, [], []
    if job.text == UNSUPPORTED_TEXT or job.state == "unsupported":
        return UNSUPPORTED_TEXT, [], []
    return _draft_supported(job, model_client)


def _draft_supported(job: IncomingMessage, model_client: ModelClient):
    active = SourceSnapshot.objects.filter(is_active=True).first()
    safe_text = minimize_text(job.text)
    if safe_text is None or active is None or active.version != job.snapshot_version:
        return FAILURE_TEXT, [], []
    arguments: _TurnArguments = {
        "sender": job.sender,
        "model_client": TrackedModelClient(job, model_client),
        "snapshot_version": job.snapshot_version,
    }
    history = conversation_history(job)
    if history:
        arguments["history"] = history
    result = run_turn(
        safe_text,
        **arguments,
    )
    return result["text"], result["operations"], safe_sources(result["sources"])


@transaction.atomic
def _prepare_reply(
    job: IncomingMessage,
    text: str,
    operations: list[dict[str, Any]],
    sources: list[dict[str, Any]],
) -> OutgoingReply | None:
    job.refresh_from_db()
    if job.state != "running" or job.worker_generation != GENERATION or not owns():
        return None
    conversation = job.conversation
    conversation.refresh_from_db()
    if not _set_mode(conversation, text):
        job.state = "routed_to_operator"
        job.save(update_fields=["state"])
        return None
    job.state = "completed"
    job.operation_log = operations
    job.sources = sources
    job.save(update_fields=["state", "operation_log", "sources"])
    reply, _ = OutgoingReply.objects.get_or_create(source=job, defaults={"text": text})
    return reply


def _set_mode(conversation, text):
    if text != HANDOFF_TEXT:
        return conversation.mode == "automation"
    if conversation.mode == "automation":
        conversation_model = conversation.__class__
        conversation_model.objects.filter(pk=conversation.pk, mode="automation").update(
            mode="human_pending"
        )
        conversation.refresh_from_db()
    return conversation.mode in {"human_pending", "human_active"}


def _resume_queued() -> OutgoingReply | None:
    queued = Q(state="queued", source__state="completed") | Q(
        state="notification_pending", source__state="notification_pending"
    )
    reply = OutgoingReply.objects.filter(queued).order_by("created_at").first()
    if reply is None or not owns():
        return None
    if reply.state == "notification_pending":
        reply.text = FAILURE_TEXT
        reply.state = "queued"
        reply.save(update_fields=["text", "state"])
    return reply
