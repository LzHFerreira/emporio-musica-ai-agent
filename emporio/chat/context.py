"""Build a bounded same-customer history from accepted, current-source turns."""

import json

from django.db.models import Q

from emporio.chat.models import IncomingMessage
from emporio.chat.privacy import minimize_text
from emporio.orders_access import sender_binding

MAX_HISTORY_MESSAGES = 10
MAX_HISTORY_BYTES = 12 * 1024


def conversation_history(job):
    """Return safe chronological user/assistant messages for this conversation."""
    binding = _current_binding(job)
    if binding is None:
        return []
    return _history_messages(job, binding)


def _current_binding(job):
    if job.sender != job.conversation.sender:
        return None
    binding = sender_binding(job.sender, job.snapshot_version)
    return binding if binding == job.customer_binding else None


def _history_messages(job, binding):
    prior = (
        IncomingMessage.objects.filter(
            conversation_id=job.conversation_id,
            sender=job.sender,
            snapshot_version=job.snapshot_version,
            customer_binding=binding,
            state="completed",
            outgoingreply__state__in=("accepted", "delivered", "read"),
        )
        .exclude(pk=job.pk)
        .filter(Q(received_at__lt=job.received_at) | Q(received_at=job.received_at, pk__lt=job.pk))
        .order_by("-received_at", "-pk")[: MAX_HISTORY_MESSAGES // 2]
    )
    pairs = [_accepted_pair(item) for item in prior]
    return _bounded_messages([pair for pair in pairs if pair])


def _accepted_pair(job):
    user = minimize_text(job.text)
    assistant = minimize_text(job.outgoingreply.text)
    if user is None or assistant is None:
        return []
    return [{"role": "user", "content": user}, {"role": "assistant", "content": assistant}]


def _bounded_messages(pairs):
    selected = []
    size = 0
    for pair in pairs:
        encoded = json.dumps(pair, ensure_ascii=False).encode("utf-8")
        if size + len(encoded) > MAX_HISTORY_BYTES:
            continue
        selected.insert(0, pair)
        size += len(encoded)
    return [message for pair in selected for message in pair]
