"""Run one bounded model turn over the registered tool boundary."""

from collections.abc import Callable
from typing import Any

from django.db.utils import DatabaseError

from emporio.agent_output import output_supported
from emporio.agent_protocol import FAILURE_TEXT, HANDOFF_TEXT, SYSTEM_PROMPT, result, terminal
from emporio.agent_schemas import TOOL_SCHEMAS
from emporio.agent_tools import ToolHandler, execute_calls
from emporio.catalog.models import SourceSnapshot
from emporio.chat.privacy import minimize_text


def run_turn(
    text: str,
    *,
    sender: str,
    model_client: Callable[..., dict[str, Any]],
    snapshot_version: str | None,
    handlers: dict[str, ToolHandler],
    history: list[dict[str, str]] | None = None,
) -> dict[str, Any]:
    """Execute no more than three model requests using one pinned source version."""
    version = _turn_version(snapshot_version)
    safe_text = minimize_text(text)
    state = _new_state()
    if not _valid_turn(safe_text, snapshot_version):
        return _fallback(state, version or "")
    messages = _initial_messages(safe_text, history)
    return _loop(messages, sender, model_client, version or "", handlers, state)


def _turn_version(snapshot_version):
    return snapshot_version if snapshot_version is not None else _active_version()


def _initial_messages(text, history):
    return [
        {"role": "system", "content": SYSTEM_PROMPT},
        *(history or []),
        {"role": "user", "content": text},
    ]


def _new_state():
    return {"sources": [], "operations": [], "evidence": [], "requests": 0, "executions": 0}


def _valid_turn(text, version):
    return text is not None and (version is None or isinstance(version, str))


def _loop(messages, sender, model_client, version, handlers, state):
    for _ in range(3):
        response = _request(model_client, messages, state)
        if response is None:
            break
        keep_going, answer = _step(
            response, messages, sender, model_client, version, handlers, state
        )
        if answer is not None:
            return answer
        if not keep_going:
            break
    return _fallback(state, version)


def _step(response, messages, sender, model_client, version, handlers, state):
    calls = response.get("tool_calls")
    if calls:
        done = execute_calls(
            calls,
            messages,
            sender,
            model_client,
            version,
            handlers,
            state,
            response.get("provider_content"),
        )
        return done, None
    return _terminal_result(response.get("content"), state, version)


def _terminal_result(content, state, version):
    answer = terminal(content)
    if (
        answer is None
        or answer["outcome"] != "handoff"
        and not output_supported(
            answer["text"], answer["outcome"], state["sources"], state["evidence"]
        )
    ):
        return False, None
    text = HANDOFF_TEXT if answer["outcome"] == "handoff" else answer["text"]
    return False, _envelope(answer, text, state, version)


def _request(model_client, messages, state):
    state["requests"] += 1
    try:
        response = model_client(messages, TOOL_SCHEMAS)
    except Exception:
        return None
    return response if isinstance(response, dict) else None


def _envelope(answer, text, state, version):
    return result(
        answer["outcome"],
        text,
        answer["reason"],
        state["sources"],
        state["operations"],
        state["requests"],
        state["executions"],
        version,
    )


def _fallback(state, version):
    return result(
        "answer",
        FAILURE_TEXT,
        None,
        state["sources"],
        state["operations"],
        state["requests"],
        state["executions"],
        version,
    )


def _active_version() -> str:
    try:
        active = SourceSnapshot.objects.filter(is_active=True).first()
        return active.version if active else ""
    except (DatabaseError, AttributeError):
        return ""
