"""Persist provider budget counters before invoking external model boundaries."""

from collections.abc import Callable
from time import monotonic
from typing import Any

from django.db.models import F
from django.utils import timezone

from emporio.chat.models import IncomingMessage


class TrackedModelClient:
    """Wrap a model callback with durable, generation-fenced counters."""

    def __init__(self, job: IncomingMessage, client: Callable[..., dict[str, Any]]) -> None:
        """Retain the job and callback whose attempts must be persisted."""
        self.job = job
        self.client = client
        model = getattr(client, "model", "")
        self.model = model if isinstance(model, str) else ""
        remaining = (job.deadline - timezone.now()).total_seconds() - 5
        self._work_deadline = monotonic() + max(0, remaining)

    def __call__(self, messages, tools):
        """Persist a request count, then call the provider adapter."""
        self._remaining()
        self._increment("model_requests", requested_model=self.model[:160])
        remaining = self._remaining()
        timed_client: Any = self.client
        previous = getattr(timed_client, "request_timeout", None)
        bounded = isinstance(previous, (int, float))
        if bounded:
            timed_client.request_timeout = min(previous, remaining)
        try:
            result = self.client(messages, tools)
        finally:
            if bounded:
                timed_client.request_timeout = previous
        self._remaining()
        self._provider_metadata()
        return result

    def before_tool(self) -> None:
        """Persist a tool attempt before invoking its handler."""
        self._remaining()
        self._increment("tool_executions")
        self._remaining()

    def _remaining(self) -> float:
        remaining = self._work_deadline - monotonic()
        if remaining <= 0:
            raise TimeoutError("Model/tool work deadline exhausted")
        return remaining

    def _increment(self, field: str, **values) -> None:
        from emporio.chat.lease import GENERATION

        updated = IncomingMessage.objects.filter(
            pk=self.job.pk, state="running", worker_generation=GENERATION
        ).update(**{field: F(field) + 1, **values})
        if not updated:
            raise RuntimeError("worker generation is no longer current")

    def _provider_metadata(self) -> None:
        from emporio.chat.lease import GENERATION

        values = {
            "returned_model": str(getattr(self.client, "returned_model", ""))[:160],
            "returned_provider": str(getattr(self.client, "returned_provider", ""))[:80],
        }
        IncomingMessage.objects.filter(
            pk=self.job.pk, state="running", worker_generation=GENERATION
        ).update(**values)
