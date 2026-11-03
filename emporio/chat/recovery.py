"""Mark uncertain work terminal during restart recovery."""

from django.db import transaction
from django.db.models import Q
from django.utils import timezone

from emporio.chat.models import IncomingMessage, OutgoingReply, WorkerLease


@transaction.atomic
def recover_interrupted() -> tuple[int, int]:
    """Interrupt model work and mark in-flight provider sends unknown."""
    lease = WorkerLease.objects.filter(key="default", expires_at__gt=timezone.now()).first()
    stale = (
        Q() if lease is None else Q(worker_generation="") | ~Q(worker_generation=lease.generation)
    )
    jobs = IncomingMessage.objects.filter(state="running").filter(stale).update(state="interrupted")
    sends_query = OutgoingReply.objects.filter(state="sending")
    if lease is not None:
        sends_query = sends_query.filter(
            Q(source__worker_generation="") | ~Q(source__worker_generation=lease.generation)
        )
    sends = sends_query.update(state="unknown")
    return jobs, sends
