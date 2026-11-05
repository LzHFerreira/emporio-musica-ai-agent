"""Acquire and renew the singleton worker generation lease."""

from datetime import timedelta
from threading import Event
from uuid import uuid4

from django.db.models import Q
from django.utils import timezone

from emporio.chat.models import WorkerLease

GENERATION = uuid4().hex
LEASE_SECONDS = 5


def acquire() -> bool:
    """Renew this process lease or take an expired singleton lease."""
    now = timezone.now()
    WorkerLease.objects.get_or_create(
        key="default", defaults={"generation": GENERATION, "expires_at": now, "renewed_at": now}
    )
    return bool(
        WorkerLease.objects.filter(key="default")
        .filter(Q(generation=GENERATION) | Q(expires_at__lte=now))
        .update(
            generation=GENERATION, expires_at=now + timedelta(seconds=LEASE_SECONDS), renewed_at=now
        )
    )


def owns() -> bool:
    """Check that this process remains the current unexpired worker."""
    return WorkerLease.objects.filter(
        key="default", generation=GENERATION, expires_at__gt=timezone.now()
    ).exists()


def release() -> None:
    """Expire this process lease so the next generation can take the singleton."""
    WorkerLease.objects.filter(key="default", generation=GENERATION).update(
        expires_at=timezone.now()
    )


def heartbeat(stop: Event) -> None:
    """Renew the lease once a second while a provider or model call is active."""
    while not stop.wait(1):
        now = timezone.now()
        changed = WorkerLease.objects.filter(key="default", generation=GENERATION).update(
            expires_at=now + timedelta(seconds=LEASE_SECONDS), renewed_at=now
        )
        if not changed:
            return
