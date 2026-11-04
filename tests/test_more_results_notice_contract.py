import json

from django.core.management import call_command
from django.test import TestCase

from emporio.agent import run_turn
from emporio.agent_protocol import MORE_RESULTS_TEXT
from tests.test_agent_contract import DATA_DIR, tool_call

REPLY = "Temos várias opções de violão no catálogo."


class MoreResultsNoticeContractTests(TestCase):
    def setUp(self):
        call_command("load_sources", source_dir=str(DATA_DIR), verbosity=0)

    def run_with_reply(self, reply):
        replies = iter([
            {"tool_calls": [tool_call("search_catalog", {"query": "violão", "available_only": True})]},
            {"content": json.dumps({"outcome": "answer", "text": reply, "reason": None})},
        ])
        return run_turn("Quais violões vocês têm?", sender="5567998123456", model_client=lambda m, t: next(replies))

    def test_appends_notice_when_catalog_has_more_results(self):
        result = self.run_with_reply(REPLY)
        self.assertEqual(result["text"], REPLY + "\n\n" + MORE_RESULTS_TEXT)

    def test_keeps_reply_that_already_mentions_more_options(self):
        reply = "Temos várias opções de violão; há mais opções se quiser."
        self.assertEqual(self.run_with_reply(reply)["text"], reply)
