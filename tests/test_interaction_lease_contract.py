import json
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from django.core.management import call_command
from django.test import TransactionTestCase

from emporio.chat.local_interaction import run_interaction


DATA = Path(__file__).resolve().parents[1] / "data"
ANSWER = {"content": json.dumps({"outcome": "answer", "text": "Olá!", "reason": None})}


class InteractionLeaseContractTests(TransactionTestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA), verbosity=0)

    def test_back_to_back_interactions_release_the_worker_lease(self):
        # Each run is a separate process generation, so the second run must not
        # find the first run's lease still held.
        for generation, text in (("process-a", "Olá"), ("process-b", "Qual o horário?")):
            with patch("emporio.chat.lease.GENERATION", generation), patch("emporio.chat.worker.GENERATION", generation):
                run_interaction([text], lambda messages, tools: ANSWER, StringIO(), sender="5567998123456")
