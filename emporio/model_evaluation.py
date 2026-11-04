"""Measure live-model replies against the fixed development quality cases."""

import json
import re
import statistics
import time
from collections import Counter
from itertools import chain
from pathlib import Path
from typing import Any

from emporio.agent import run_turn
from emporio.agent_protocol import FAILURE_TEXT, HANDOFF_TEXT
from emporio.evaluation_claims import critical_hit

SENDER = "5567999990000"
FAIL_SAFE_TEXTS = {FAILURE_TEXT, HANDOFF_TEXT}
NEGATION = re.compile(r"\b(?:não|nao|nunca|nenhum|nenhuma)\b", re.IGNORECASE)
CLAUSE_BREAK = re.compile(r"[.;!?\n]+|,\s+")
DIGIT = re.compile(r"\d")
SENTENCE_BREAK = re.compile(r"[;!?\n]|\.(?!\d)")


def verdict(case: dict[str, Any], text: str) -> str:
    """Classify a reply; bind and ordered cases must hold, and negated facts fail.

    A term is negated when every clause containing it has a negation word; terms that are
    negation words themselves are exempt.
    """
    if text in FAIL_SAFE_TEXTS:
        return "FAIL-SAFE"
    if critical_hit(case, text):
        return "INCORRECT"
    return "PASS" if _passes(case, text) else "FAIL-CHECK"


def _passes(case: dict[str, Any], text: str) -> bool:
    normalized = _normalize(text)
    return (
        _checks_pass(case, normalized)
        and _bind_pass(case, text)
        and _ordered_pass(case, normalized)
        and not _negated_fact(case, text)
    )


def evaluate_model(path: Path, runs: int, model_client: Any) -> dict[str, Any]:
    """Run each case several times through the agent and summarize the verdicts."""
    cases = json.loads(path.read_text(encoding="utf-8"))
    rows = [_case_row(case, runs, model_client) for case in cases]
    total = len(cases) * runs
    passed = sum(row["passed"] for row in rows)
    return {
        "case_count": len(cases),
        "runs": runs,
        "passed": passed,
        "total": total,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        **_reply_summary(list(chain.from_iterable(row["replies"] for row in rows))),
        "cases": rows,
    }


class DraftRecorder:
    """Forward model calls and keep each raw string draft for the saved report."""

    def __init__(self, model_client: Any) -> None:
        """Wrap the client and start an empty draft list."""
        self._client = model_client
        self.drafts: list[str] = []

    def __call__(self, messages: Any, tools: Any) -> Any:
        """Record the response content when it is a string, then return the response."""
        response = self._client(messages, tools)
        content = response.get("content") if isinstance(response, dict) else None
        if isinstance(content, str):
            self.drafts.append(content)
        return response

    def __getattr__(self, name: str) -> Any:
        """Expose the wrapped client's attributes, such as `before_tool` and `model`."""
        return getattr(self._client, name)


def _reply_summary(replies: list[dict[str, Any]]) -> dict[str, Any]:
    verdicts = Counter(dict.fromkeys(("PASS", "FAIL-CHECK", "FAIL-SAFE", "ERROR"), 0))
    verdicts.update(reply["verdict"] for reply in replies)
    seconds = [reply["seconds"] for reply in replies] or [0.0]
    return {"verdicts": dict(verdicts), "median_seconds": float(statistics.median(seconds))}


def _normalize(text: str) -> str:
    return text.replace(".", "").replace(" ", "").lower()


def _find(item: str, normalized: str) -> re.Match[str] | None:
    term = re.escape(_normalize(item))
    if DIGIT.search(item):
        term = rf"(?<!\d){term}(?!\d)"
    return re.search(term, normalized)


def _hits(item: str, normalized: str) -> bool:
    return _find(item, normalized) is not None


def _bind_pass(case: dict[str, Any], text: str) -> bool:
    sentences = [_normalize(sentence) for sentence in SENTENCE_BREAK.split(text)]
    pairs = list(zip(sentences, ["", *sentences], strict=False))
    return all(_bound(a, b, pairs) for a, b in case.get("bind", []))


def _bound(a: str, b: str, pairs: list[tuple[str, str]]) -> bool:
    return any(_hits(b, now) and (_hits(a, now) or _hits(a, before)) for now, before in pairs)


def _ordered_pass(case: dict[str, Any], normalized: str) -> bool:
    spots = [_first_spot(group, normalized) for group in case.get("ordered", [])]
    return all(spot >= 0 for spot in spots) and all(
        a < b for a, b in zip(spots, spots[1:], strict=False)
    )


def _first_spot(group: list[str], normalized: str) -> int:
    spots = [match.start() for item in group if (match := _find(item, normalized))]
    return min(spots, default=-1)


def _checks_pass(case: dict[str, Any], normalized: str) -> bool:
    return (
        _all_hit(case["must"], normalized)
        and _groups_hit(case["any_groups"], normalized)
        and not _any_hit(case["forbid"], normalized)
    )


def _negated_fact(case: dict[str, Any], text: str) -> bool:
    terms = [*case["must"], *chain.from_iterable(case["any_groups"])]
    return any(_only_negated(term, text) for term in terms if not NEGATION.search(term))


def _only_negated(item: str, text: str) -> bool:
    clauses = [clause for clause in CLAUSE_BREAK.split(text) if _hits(item, _normalize(clause))]
    return bool(clauses) and all(NEGATION.search(c) for c in clauses)


def _all_hit(items: list[str], normalized: str) -> bool:
    return all(_hits(item, normalized) for item in items)


def _any_hit(items: list[str], normalized: str) -> bool:
    return any(_hits(item, normalized) for item in items)


def _groups_hit(groups: list[list[str]], normalized: str) -> bool:
    return all(_any_hit(group, normalized) for group in groups)


def _case_row(case: dict[str, Any], runs: int, model_client: Any) -> dict[str, Any]:
    replies = [_reply(case, model_client) for _ in range(runs)]
    verdicts = Counter(reply["verdict"] for reply in replies)
    return {
        "question": case["question"],
        "passed": verdicts["PASS"],
        "verdicts": dict(verdicts),
        "replies": replies,
    }


def _reply(case: dict[str, Any], model_client: Any) -> dict[str, Any]:
    started = time.monotonic()
    recorder = DraftRecorder(model_client)
    try:
        turn = run_turn(case["question"], sender=SENDER, model_client=recorder)
    except Exception as error:
        seconds = round(time.monotonic() - started, 2)
        return {
            "verdict": "ERROR",
            "seconds": seconds,
            "operations": [],
            "model_requests": None,
            "text": type(error).__name__,
            "drafts": recorder.drafts,
        }
    return {
        "verdict": verdict(case, turn["text"]),
        "seconds": round(time.monotonic() - started, 2),
        "operations": turn.get("operations", []),
        "model_requests": turn["model_requests"],
        "text": turn["text"],
        "drafts": recorder.drafts,
    }
