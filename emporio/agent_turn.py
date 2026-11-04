"""Run one bounded model turn over the registered tool boundary."""

from collections.abc import Callable
from typing import Any

from django.db.utils import DatabaseError

from emporio.agent_claims import plain_text
from emporio.agent_feedback import rejection_feedback
from emporio.agent_output import output_supported, rejection_trace
from emporio.agent_protocol import (
    FAILURE_TEXT,
    HANDOFF_TEXT,
    MORE_RESULTS_TEXT,
    OUT_OF_SCOPE_TEXT,
    SYSTEM_PROMPT,
    result,
    terminal,
)
from emporio.agent_render import with_facts
from emporio.agent_schemas import TOOL_SCHEMAS
from emporio.agent_tools import ToolHandler, execute_calls
from emporio.catalog.models import SourceSnapshot
from emporio.chat.privacy import minimize_text

_RETRY = object()


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
    if response is _RETRY:
        return True, None
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
    return _terminal_result(response.get("content"), messages, state, version)


def _terminal_result(content, messages, state, version):
    answer = with_facts(terminal(content), state["evidence"])
    if (
        answer is None
        or answer["outcome"] not in ("handoff", "out_of_scope")
        and not output_supported(
            answer["text"], answer["outcome"], state["sources"], state["evidence"]
        )
    ):
        trace = rejection_trace(answer, state["sources"], state["evidence"])
        state["operations"].append(trace)
        reply = content if isinstance(content, str) else ""
        feedback = rejection_feedback(trace["check"], answer, state["evidence"])
        messages.extend(
            [{"role": "assistant", "content": reply}, {"role": "user", "content": feedback}]
        )
        return True, None
    text = {"handoff": HANDOFF_TEXT, "out_of_scope": OUT_OF_SCOPE_TEXT}.get(
        answer["outcome"], answer["text"]
    )
    text = _with_more_notice(answer["outcome"], text, state["evidence"])
    return False, _envelope(answer, text, state, version)


def _with_more_notice(outcome, text, evidence):
    if outcome == "answer" and not _mentions_more(text) and any(map(_catalog_has_more, evidence)):
        return text + "\n\n" + MORE_RESULTS_TEXT
    return text


def _mentions_more(text):
    plain = plain_text(text)
    return any(term in plain for term in ("mais opcoes", "outras opcoes", "mais resultados"))


def _catalog_has_more(item):
    sources = item.get("sources", []) if isinstance(item, dict) else []
    return bool(item.get("has_more")) and any(s.get("type") == "catalog" for s in sources)


def _request(model_client, messages, state):
    state["requests"] += 1
    try:
        response = model_client(messages, TOOL_SCHEMAS)
    except ValueError:
        return _RETRY
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
