"""NFR-05 command contracts for the source-pinned retrieval evaluator."""

import json
import tempfile
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from emporio.catalog.models import SourceSnapshot
from emporio.policy import lookup_public_policy
from tests.test_source_workflow_fixture import SourceWorkflowFixture

FIXTURE = Path(__file__).parent / "fixtures" / "retrieval_quality.json"


class RetrievalEvaluatorCommandTests(SourceWorkflowFixture):
    def test_command_emits_metrics_and_calls_the_pinned_public_lookup(self):
        output = StringIO()
        with patch("emporio.policy_evaluation.lookup_public_policy", wraps=lookup_public_policy) as lookup:
            call_command("evaluate_retrieval", cases=str(FIXTURE), stdout=output)
        report = json.loads(output.getvalue())
        self.assertTrue(report["all_cases_passed"])
        self.assertEqual(report["case_count"], 11)
        self.assertEqual((report["section_precision"], report["section_recall"]), (1.0, 1.0))
        self.assertEqual(report["condition_coverage"], 1.0)
        self.assertEqual((report["internal_leakage_count"], report["irrelevant_result_count"]), (0, 0))
        self.assertGreaterEqual(report["p95_seconds"], 0)
        self.assertEqual(lookup.call_args.kwargs["snapshot_version"], report["snapshot_version"])

    def test_missing_invalid_and_empty_case_files_fail_clearly(self):
        with tempfile.TemporaryDirectory() as root:
            missing = Path(root) / "missing.json"
            malformed = self._write(Path(root) / "malformed.json", "{")
            empty = self._write(Path(root) / "empty.json", "[]")
            for path in (missing, malformed, empty):
                with self.subTest(path=path.name), self.assertRaises(CommandError):
                    call_command("evaluate_retrieval", cases=str(path), stdout=StringIO())

    def test_no_active_source_snapshot_fails_clearly(self):
        SourceSnapshot.objects.update(is_active=False)
        with self.assertRaisesRegex(CommandError, "no active source snapshot"):
            call_command("evaluate_retrieval", cases=str(FIXTURE), stdout=StringIO())

    def test_nonpublic_returned_data_fails_threshold_and_is_counted(self):
        public = self._public_passage()
        private = {**public, "text": public["text"] + " private content"}
        report = self._failing_report(self._case([public["section"]]), {
            "outcome": "found", "data": [private], "sources": [],
        })
        self.assertEqual(report["internal_leakage_count"], 1)
        self.assertFalse(report["all_cases_passed"])

    def test_missing_evidence_and_irrelevant_results_fail_threshold(self):
        public = self._public_passage()
        missing = self._failing_report(self._case([public["section"]]), {
            "outcome": "not_found", "data": [], "sources": [],
        })
        irrelevant = self._failing_report(self._case([]), {
            "outcome": "found", "data": [public], "sources": [],
        })
        self.assertFalse(missing["all_cases_passed"])
        self.assertGreater(irrelevant["irrelevant_result_count"], 0)
        self.assertFalse(irrelevant["all_cases_passed"])

    def _public_passage(self):
        snapshot = self.snapshot
        return next(item for item in snapshot.manifest["policy"]["passages"] if item["audience"] == "public")

    def _case(self, sections):
        return [{"id": "test", "split": "contract", "query": "a source question", "topic": None,
                 "sections": sections, "conditions": []}]

    def _failing_report(self, cases, result):
        with tempfile.TemporaryDirectory() as root:
            path = self._write(Path(root) / "case.json", json.dumps(cases))
            output = StringIO()
            with patch("emporio.policy_evaluation.lookup_public_policy", return_value=result):
                with self.assertRaises(CommandError):
                    call_command("evaluate_retrieval", cases=str(path), stdout=output)
            return json.loads(output.getvalue())

    def _write(self, path, text):
        path.write_text(text, encoding="utf-8")
        return path
