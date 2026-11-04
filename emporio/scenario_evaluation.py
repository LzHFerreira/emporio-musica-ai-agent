"""Replay multi-turn customer scenarios through the agent and summarize the verdicts."""

import json
import time
from pathlib import Path
from typing import Any

from emporio.agent import run_turn
from emporio.model_evaluation import SENDER, DraftRecorder, _reply_summary, verdict


def evaluate_scenarios(path: Path, runs: int, model_client: Any) -> dict[str, Any]:
    """Run each scenario several times, carrying the conversation history between turns."""
    scenarios = json.loads(path.read_text(encoding="utf-8"))
    rows = [_scenario_row(scenario, runs, model_client) for scenario in scenarios]
    turns = [turn for row in rows for run in row["runs"] for turn in run]
    return {
        "scenario_count": len(scenarios),
        "turn_count": len(turns),
        **_reply_summary(turns),
        "scenarios": rows,
    }


def _scenario_row(scenario: dict[str, Any], runs: int, model_client: Any) -> dict[str, Any]:
    sender = scenario["sender"] or SENDER
    runs_rows = [_run(scenario["turns"], sender, model_client) for _ in range(runs)]
    return {"id": scenario["id"], "category": scenario["category"], "runs": runs_rows}


def _run(turns: list[dict[str, Any]], sender: str, model_client: Any) -> list[dict[str, Any]]:
    history: list[dict[str, str]] = []
    rows = []
    for turn in turns:
        row = _turn(turn, sender, history, model_client)
        history.append({"role": "user", "content": turn["customer"]})
        history.append({"role": "assistant", "content": row["text"]})
        rows.append(row)
    return rows


def _turn(
    turn: dict[str, Any], sender: str, history: list[dict[str, str]], model_client: Any
) -> dict[str, Any]:
    started = time.monotonic()
    judged = "ERROR"
    recorder = DraftRecorder(model_client)
    try:
        result = run_turn(
            turn["customer"], sender=sender, model_client=recorder, history=list(history)
        )
        judged = verdict(turn, result["text"])
    except Exception as error:
        result = {"text": type(error).__name__, "model_requests": None}
    return {
        "customer": turn["customer"],
        "verdict": judged,
        "text": result["text"],
        "seconds": round(time.monotonic() - started, 2),
        "operations": result.get("operations", []),
        "model_requests": result["model_requests"],
        "drafts": recorder.drafts,
    }
