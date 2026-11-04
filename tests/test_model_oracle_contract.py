"""Contracts pairing labeled oracle replies with the live-reply verdict rules."""

import json
from pathlib import Path

from django.test import SimpleTestCase

from emporio.model_evaluation import verdict

FIXTURES = Path(__file__).parent / "fixtures"
CASES = json.loads((FIXTURES / "model_quality.json").read_text(encoding="utf-8"))
ORACLE = json.loads((FIXTURES / "model_oracle.json").read_text(encoding="utf-8"))


def _case(question):
    return next(case for case in CASES if case["question"] == question)


class ModelOracleContractTests(SimpleTestCase):
    def _check_label(self, label, expected):
        for row in (row for row in ORACLE if row["label"] == label):
            with self.subTest(question=row["question"], reply=row["reply"]):
                self.assertEqual(verdict(_case(row["question"]), row["reply"]), expected)

    def test_wrong_replies_fail_the_check(self):
        self._check_label("wrong", "FAIL-CHECK")

    def test_right_replies_pass(self):
        self._check_label("right", "PASS")
