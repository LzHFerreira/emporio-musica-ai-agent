"""Evaluator dimensions reported separately from the outcome verdict."""

from typing import Any

from emporio.evaluation_claims import critical_hit
from emporio.model_evaluation import FAIL_SAFE_TEXTS, _passes, verdict


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
    }
