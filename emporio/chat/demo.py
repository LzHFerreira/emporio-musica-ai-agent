"""Run five signed, loopback-only interactions through the real chat boundary."""

from time import time

import httpx
from django.conf import settings
from django.core.management.base import CommandError
from django.utils import timezone

from emporio.agent_protocol import FAILURE_TEXT, HANDOFF_TEXT
from emporio.catalog.models import SourceSnapshot
from emporio.chat.demo_http import MetaAcceptanceServer, signed_post, webhook_server
from emporio.chat.demo_script import CASES, ScriptedModelClient
from emporio.chat.meta import MetaClient
from emporio.chat.models import IncomingMessage, OutgoingReply
from emporio.chat.worker import process_next


def run_demo():
    """Run and summarize five signed webhook turns using actual tools and worker."""
    snapshot = SourceSnapshot.objects.filter(is_active=True).first()
    if snapshot is None:
        raise CommandError("load canonical sources before running demo_chat")
    _require_idle_worker()
    rows = _run_cases(snapshot.version)
    return _report(rows)


def _run_cases(version):
    rows = []
    with MetaAcceptanceServer() as provider, webhook_server() as webhook:
        with httpx.Client(timeout=3) as client:
            sender = MetaClient(base_url=provider.base_url, token="local-demo-only", client=client)
            for index, case in enumerate(CASES, start=1):
                rows.append(_run_case(index, case, version, webhook, provider, sender))
    return rows


def _run_case(index, case, version, webhook, provider, sender):
    sender_id = _synthetic_sender(provider.run_id, index)
    _require_status(
        _post_message(webhook, provider.run_id, index, sender_id, case["text"]),
        200,
        "message",
    )
    model = ScriptedModelClient(case)
    reply = process_next(model_client=model, send_client=sender)
    if reply is None or reply.state != "accepted":
        raise CommandError(f"demo turn did not reach provider acceptance: {case['case']}")
    if provider.accepted[-1] != reply.provider_id:
        raise CommandError("mock Meta acceptance did not match the stored reply")
    accepted = reply.source.model_requests, reply.source.tool_executions
    _require_status(_post_delivery(webhook, reply.provider_id, sender_id), 200, "delivery")
    reply.refresh_from_db()
    if reply.state != "delivered":
        raise CommandError(f"demo delivery callback was not applied: {case['case']}")
    reply.source.refresh_from_db()
    _validate_answer(case, reply.text)
    return _interaction(case, version, accepted, reply)


def _require_idle_worker():
    active = ("pending", "unsupported", "notification_pending", "running")
    pending_jobs = IncomingMessage.objects.filter(state__in=active).exists()
    pending_replies = OutgoingReply.objects.filter(
        state__in=("queued", "notification_pending")
    ).exists()
    if pending_jobs or pending_replies:
        raise CommandError("demo requires an idle worker queue; process existing work first")


def _synthetic_sender(run_id, index):
    number = int(run_id[:8], 16) % 1_000_000_000 + index
    return f"1555{number:09d}"


def _validate_answer(case, answer):
    if answer == FAILURE_TEXT or (case["answer"] == "handoff") != (answer == HANDOFF_TEXT):
        raise CommandError(f"demo turn did not pass terminal response validation: {case['case']}")


def _post_message(webhook, run_id, index, sender, text):
    message = {
        "from": sender,
        "id": f"demo-in-{run_id}-{index}",
        "timestamp": str(int(time())),
        "type": "text",
        "text": {"body": text},
    }
    return signed_post(webhook, _envelope({"messages": [message]}), settings.META_APP_SECRET)


def _post_delivery(webhook, provider_id, sender):
    status = {
        "id": provider_id,
        "recipient_id": sender,
        "status": "delivered",
        "timestamp": str(int(timezone.now().timestamp())),
    }
    return signed_post(webhook, _envelope({"statuses": [status]}), settings.META_APP_SECRET)


def _envelope(value):
    return {
        "object": "whatsapp_business_account",
        "entry": [
            {
                "id": settings.META_BUSINESS_ID,
                "changes": [
                    {
                        "value": {
                            "messaging_product": "whatsapp",
                            "metadata": {"phone_number_id": settings.META_PHONE_NUMBER_ID},
                            **value,
                        }
                    }
                ],
            }
        ],
    }


def _interaction(case, version, budgets, reply):
    job_counts = {"model_requests": budgets[0], "tool_executions": budgets[1]}
    outcome = "handoff" if case["answer"] == "handoff" else "answer"
    source_types = {source["type"] for source in reply.source.sources if source.get("type")}
    return {
        "case": case["case"],
        "question": case["text"],
        "answer": reply.text,
        "outcome": outcome,
        "source_types": sorted(source_types),
        "snapshot_version": version,
        **job_counts,
        "provider_accepted": True,
        "delivery_confirmed": reply.state in {"delivered", "read"},
        "reply_state": reply.state,
    }


def _report(rows):
    accepted = sum(row["provider_accepted"] for row in rows)
    delivered = sum(row["delivery_confirmed"] for row in rows)
    return {
        "model_mode": "scripted",
        "notice": "Deterministic scripted model adapter; not evidence of live LLM answer quality.",
        "interaction_count": len(rows),
        "accepted_count": accepted,
        "delivered_count": delivered,
        "interactions": rows,
    }


def _require_status(actual, expected, phase):
    if actual != expected:
        raise CommandError(f"local webhook {phase} callback returned HTTP status {actual}")
