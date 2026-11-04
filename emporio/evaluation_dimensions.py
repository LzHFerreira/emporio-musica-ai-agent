"""Evaluator dimensions reported separately from the outcome verdict."""

import re
from typing import Any

from emporio.evaluation_claims import critical_hit, fold
from emporio.model_evaluation import FAIL_SAFE_TEXTS, _passes, verdict

ABSTAIN_MARKERS = (
    "nao sei",
    "nao tenho essa informacao",
    "nao consta",
    "nao encontrei",
    "nao posso confirmar",
    "recomendo confirmar",
)


def _uncertainty(case: dict[str, Any], text: str) -> str:
    if "expect" not in case:
        return "n/a"
    folded = fold(text)
    if case["expect"] == "clarification":
        ok = "?" in text and not re.search(r"r\$\s*\d", folded)
    else:
        ok = any(marker in folded for marker in ABSTAIN_MARKERS)
    return "pass" if ok else "fail"


def assess(case: dict[str, Any], text: str) -> dict[str, str]:
    """Score a reply per dimension, returning the outcome verdict and pass/fail flags.

    Args:
        case: Evaluation case with optional critical claims and check rules.
        text: Model reply to score.
    """
    return {
        "outcome": verdict(case, text),
        "factual": "fail" if critical_hit(case, text) else "pass",
        "lexical": "pass" if _passes(case, text) else "fail",
        "execution": "fail" if text in FAIL_SAFE_TEXTS else "pass",
        "uncertainty": _uncertainty(case, text),
    }
