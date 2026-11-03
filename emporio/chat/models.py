"""Persist minimized chat work and provider delivery evidence."""

from django.db import models


class Conversation(models.Model):
    """Track automation state for one authenticated channel sender."""

    sender = models.CharField(max_length=32, unique=True)
    mode = models.CharField(max_length=20, default="automation")
    last_customer_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class IncomingMessage(models.Model):
    """Store one minimized, deduplicated customer message and worker state."""

    conversation = models.ForeignKey(Conversation, on_delete=models.PROTECT)
    provider_id = models.CharField(max_length=200, unique=True)
    sender = models.CharField(max_length=32)
    fingerprint = models.CharField(max_length=64, blank=True)
    text = models.TextField()
    state = models.CharField(max_length=24, default="pending")
    received_at = models.DateTimeField()
    occurred_at = models.DateTimeField()
    deadline = models.DateTimeField()
    snapshot_version = models.CharField(max_length=64, blank=True)
    reply_to_id = models.CharField(max_length=200, blank=True)
    operation_log = models.JSONField(default=list)
    sources = models.JSONField(default=list)
    prompt_version = models.CharField(max_length=40, default="store-assistant-v1")
    customer_binding = models.CharField(max_length=32, blank=True)
    requested_model = models.CharField(max_length=160, blank=True)
    returned_model = models.CharField(max_length=160, blank=True)
    returned_provider = models.CharField(max_length=80, blank=True)
    model_requests = models.PositiveSmallIntegerField(default=0)
    tool_executions = models.PositiveSmallIntegerField(default=0)
    worker_generation = models.CharField(max_length=64, blank=True)
    notification_only = models.BooleanField(default=False)


class OutgoingReply(models.Model):
    """Persist validated reply text before making a provider request."""

    source = models.OneToOneField(IncomingMessage, on_delete=models.PROTECT)
    text = models.TextField()
    state = models.CharField(max_length=24, default="queued")
    provider_id = models.CharField(max_length=200, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    send_started_at = models.DateTimeField(null=True, blank=True)
    delivery_at = models.DateTimeField(null=True, blank=True)
    failure_reason = models.CharField(max_length=32, blank=True)


class WorkerLease(models.Model):
    """Represent the single active worker generation and lease expiry."""

    key = models.CharField(max_length=32, primary_key=True, default="default")
    generation = models.CharField(max_length=64)
    expires_at = models.DateTimeField()
    renewed_at = models.DateTimeField()


class DeliveryEvent(models.Model):
    """Retain a scoped callback that arrived before send acceptance commits."""

    phone_number_id = models.CharField(max_length=64)
    provider_id = models.CharField(max_length=200)
    recipient_id = models.CharField(max_length=32)
    status = models.CharField(max_length=16)
    occurred_at = models.DateTimeField()
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        """Deduplicate exact provider delivery evidence."""

        constraints = [
            models.UniqueConstraint(
                fields=("phone_number_id", "provider_id", "recipient_id", "status", "occurred_at"),
                name="chat_delivery_event_unique",
            )
        ]
