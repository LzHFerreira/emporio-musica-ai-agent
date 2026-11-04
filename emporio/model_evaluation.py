"""Measure live-model replies against the fixed development quality cases."""

import json
import re
from collections import Counter
from itertools import chain
from pathlib import Path
from typing import Any

from emporio.agent import run_turn
from emporio.agent_protocol import FAILURE_TEXT, HANDOFF_TEXT

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
        "cases": rows,
    }


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
    try:
        turn = run_turn(case["question"], sender=SENDER, model_client=model_client)
    except Exception as error:
        return {"verdict": "ERROR", "model_requests": None, "text": type(error).__name__}
    return {
        "verdict": verdict(case, turn["text"]),
        "model_requests": turn["model_requests"],
        "text": turn["text"],
    }
