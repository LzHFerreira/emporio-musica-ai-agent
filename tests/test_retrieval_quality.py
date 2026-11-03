"""Evaluate policy retrieval against fixed development and held-out queries."""

import json
import math
from pathlib import Path
from time import perf_counter

from emporio.policy import lookup_public_policy
from tests.test_source_workflow_fixture import SourceWorkflowFixture

CASES = Path(__file__).parent / "fixtures" / "retrieval_quality.json"


class RetrievalQualityTests(SourceWorkflowFixture):
    def test_expected_sections_conditions_and_internal_exclusion(self):
        cases = json.loads(CASES.read_text(encoding="utf-8"))
        latencies, relevant, retrieved, required, covered = [], 0, 0, 0, 0
        for case in cases:
            with self.subTest(split=case["split"], case=case["id"]):
                result, elapsed = self._lookup(case)
                latencies.append(elapsed)
                sections = self._sections(result)
                expected = set(case["sections"])
                relevant += len(sections & expected)
                retrieved += len(sections)
                required += len(case["conditions"])
                covered += self._conditions_covered(case, result)
                self.assertEqual(
                    self._conditions_covered(case, result), len(case["conditions"]),
                    (case["id"], self._missing_conditions(case, result)),
                )
                self.assertEqual(sections, expected, (case["id"], sections))
        self.assertEqual(relevant / max(1, retrieved), 1.0, self._metrics(latencies, relevant, retrieved, required, covered))
        self.assertEqual(covered / max(1, required), 1.0, self._metrics(latencies, relevant, retrieved, required, covered))

    def _lookup(self, case):
        start = perf_counter()
        result = lookup_public_policy(query=case["query"], topic=case["topic"])
        return result, perf_counter() - start

    def _sections(self, result):
        self.assertLessEqual(len(result["data"]), 3)
        self.assertTrue(all("audience" not in item for item in result["data"]))
        return {item["section"] for item in result["data"]}

    def _conditions_covered(self, case, result):
        text = " ".join(item["text"].casefold() for item in result["data"])
        return sum(term.casefold() in text for term in case["conditions"])

    def _missing_conditions(self, case, result):
        text = " ".join(item["text"].casefold() for item in result["data"])
        return [term for term in case["conditions"] if term.casefold() not in text]

    def _metrics(self, latencies, relevant, retrieved, required, covered):
        p95 = sorted(latencies)[math.ceil(0.95 * len(latencies)) - 1]
        return f"section_precision={relevant / max(1, retrieved):.3f}, condition_coverage={covered / max(1, required):.3f}, p95_seconds={p95:.4f}"
