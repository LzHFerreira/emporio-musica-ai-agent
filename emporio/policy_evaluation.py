"""Evaluate source-bound, deterministic policy retrieval quality."""

import json
import math
from pathlib import Path
from time import perf_counter

from django.core.management.base import CommandError

from emporio.catalog.models import SourceSnapshot
from emporio.policy import lookup_public_policy


def evaluate_retrieval(path: Path):
    """Read fixed cases, pin one active source snapshot, and calculate metrics."""
    cases = _read_cases(path)
    snapshot = SourceSnapshot.objects.filter(is_active=True).first()
    if snapshot is None:
        raise CommandError("no active source snapshot is available")
    public = _public_fingerprints(snapshot.manifest)
    rows = [_case_row(case, snapshot.version, public) for case in cases]
    return _report(rows, snapshot.version)


def _read_cases(path):
    try:
        cases = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise CommandError(f"cannot read retrieval cases: {path}") from error
    if not isinstance(cases, list) or not cases:
        raise CommandError("retrieval case fixture must be a nonempty JSON list")
    return cases


def _public_fingerprints(manifest):
    passages = manifest.get("policy", {}).get("passages", [])
    return {
        _fingerprint(item)
        for item in passages
        if isinstance(item, dict) and item.get("audience") == "public"
    }


def _fingerprint(item):
    return tuple(item.get(key) for key in ("text", "topic", "page", "section", "conflict"))


def _lookup(case, version):
    start = perf_counter()
    result = lookup_public_policy(
        query=case["query"], topic=case["topic"], snapshot_version=version
    )
    return result, perf_counter() - start


def _case_row(case, version, public):
    result, elapsed = _lookup(case, version)
    sections = {item.get("section") for item in result["data"]}
    expected = set(case["sections"])
    hits = len(sections & expected)
    covered = sum(term.casefold() in _text(result) for term in case["conditions"])
    leakage = sum(_fingerprint(item) not in public for item in result["data"])
    return _case_metrics(case, result, elapsed, sections, expected, hits, covered, leakage)


def _text(result):
    return " ".join(item.get("text", "").casefold() for item in result["data"])


def _case_metrics(case, result, elapsed, sections, expected, hits, covered, leakage):
    conditions = len(case["conditions"])
    precision = _precision(hits, sections, expected)
    recall = _recall(hits, expected, sections)
    coverage = covered / conditions if conditions else 1.0
    expected_outcome = "found" if expected else "not_found"
    return {
        "id": case["id"],
        "split": case["split"],
        "outcome": result["outcome"],
        "expected_outcome": expected_outcome,
        "expected_sections": case["sections"],
        "returned_sections": sorted(sections),
        "section_precision": precision,
        "section_recall": recall,
        "conditions_covered": covered,
        "conditions_required": conditions,
        "condition_coverage": coverage,
        "internal_leakage_count": leakage,
        "latency_seconds": elapsed,
        "passed": _case_passed(result, expected_outcome, precision, recall, coverage, leakage),
    }


def _precision(hits, sections, expected):
    return hits / len(sections) if sections else float(not expected)


def _recall(hits, expected, sections):
    return hits / len(expected) if expected else float(not sections)


def _case_passed(result, expected_outcome, precision, recall, coverage, leakage):
    return (
        result["outcome"] == expected_outcome
        and precision == recall == coverage == 1.0
        and leakage == 0
    )


def _report(rows, version):
    return {
        "snapshot_version": version,
        "case_count": len(rows),
        "section_precision": _ratio(rows, "section_precision"),
        "section_recall": _ratio(rows, "section_recall"),
        "condition_coverage": _ratio(rows, "condition_coverage"),
        "internal_leakage_count": _sum_field(rows, "internal_leakage_count"),
        "irrelevant_result_count": _irrelevant_count(rows),
        "p95_seconds": _p95(rows),
        "all_cases_passed": all(row["passed"] for row in rows),
        "cases": rows,
    }


def _p95(rows):
    values = sorted(row["latency_seconds"] for row in rows)
    return values[math.ceil(0.95 * len(values)) - 1]


def _sum_field(rows, key):
    return sum(row[key] for row in rows)


def _irrelevant_count(rows):
    return sum(not row["expected_sections"] and bool(row["returned_sections"]) for row in rows)


def _ratio(rows, key):
    return sum(row[key] for row in rows) / len(rows)
