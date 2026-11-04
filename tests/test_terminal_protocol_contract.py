from unittest.mock import Mock

from django.test import TestCase

from emporio.agent import run_turn
from emporio.agent_protocol import FAILURE_TEXT

ENVELOPE = {"outcome", "text", "reason", "sources", "operations", "model_requests", "tool_executions", "snapshot_version"}
PROSE = {"content": "Olá! Em que posso ajudar?"}
ANSWER = {"content": '{"outcome": "answer", "text": "Olá! Em que posso ajudar?", "reason": null}'}
INVALID = {"tool": "output_check", "outcome": "rejected", "check": "invalid_terminal"}


def run_with(replies):
    return run_turn("Vocês vendem violão?", sender="5567998123456", model_client=Mock(side_effect=replies))


class TerminalProtocolContractTests(TestCase):
    def test_prose_on_every_attempt_fails_closed_with_documented_envelope(self):
        result = run_with([PROSE] * 5)
        self.assertEqual((set(result), result["text"]), (ENVELOPE, FAILURE_TEXT))
        self.assertIn(INVALID, result["operations"])

    def test_truncated_json_on_every_attempt_fails_closed(self):
        result = run_with([{"content": '{"outcome": "answer", "text": '}] * 5)
        self.assertEqual((set(result), result["text"]), (ENVELOPE, FAILURE_TEXT))

    def test_empty_facts_list_is_invalid_terminal(self):
        result = run_with([{"content": '{"outcome": "answer", "text": "Olá!", "reason": null, "facts": []}'}] * 5)
        self.assertIn(INVALID, result["operations"])

    def test_valid_json_retry_recovers_after_prose(self):
        result = run_with([PROSE, ANSWER])
        self.assertEqual((result["text"], result["model_requests"]), ("Olá! Em que posso ajudar?", 2))
