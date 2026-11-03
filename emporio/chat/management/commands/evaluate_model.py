"""Measure the configured live model on the fixed development question set."""

import json
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand

from emporio.chat.providers import create_model_client
from emporio.model_evaluation import evaluate_model


class Command(BaseCommand):
    """Print a JSON pass-rate report with every live reply."""

    help = "Evaluate the configured live model on fixed development questions"

    def add_arguments(self, parser):
        """Configure the case fixture and the number of runs per question."""
        parser.add_argument("--cases", default="tests/fixtures/model_quality.json")
        parser.add_argument("--runs", type=int, default=3)

    def handle(self, *args, **options):
        """Run each case live and print the measurement report."""
        client = create_model_client()
        report = evaluate_model(Path(options["cases"]), options["runs"], client)
        model = getattr(client, "model", None)
        report["model_provider"] = settings.MODEL_PROVIDER
        report["model"] = model if isinstance(model, str) else None
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
