"""Evaluate policy retrieval on the fixed, source-reviewed query fixture."""

import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError

from emporio.policy_evaluation import evaluate_retrieval


class Command(BaseCommand):
    """Print machine-readable retrieval metrics and enforce fixed thresholds."""

    help = "Evaluate policy lookup using a fixed JSON case fixture"

    def add_arguments(self, parser):
        """Configure the fixed case input path."""
        parser.add_argument("--cases", default="tests/fixtures/retrieval_quality.json")

    def handle(self, *args, **options):
        """Evaluate each case and print its pinned-source metrics."""
        report = evaluate_retrieval(Path(options["cases"]))
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
        if not report["all_cases_passed"]:
            raise CommandError("retrieval quality thresholds were not met")
