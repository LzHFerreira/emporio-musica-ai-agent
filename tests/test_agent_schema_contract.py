import json

from django.test import SimpleTestCase

from emporio.agent_protocol import result, terminal
from emporio.agent_schemas import arguments_valid, parse_call


class AgentSchemaContractTests(SimpleTestCase):
    def test_tool_call_parser_rejects_wrong_shapes_and_accepts_only_registered_object_args(self):
        malformed = (None, {}, {"type": "other"}, {"type": "function", "function": []}, {"type": "function", "function": {"name": [], "arguments": "{}"}}, {"type": "function", "function": {"name": "unknown", "arguments": "{}"}}, {"type": "function", "function": {"name": "search_catalog", "arguments": "[1]"}}, {"type": "function", "function": {"name": "search_catalog", "arguments": "{"}})
        for value in malformed:
            with self.subTest(value=value):
                self.assertIsNone(parse_call(value))
        parsed = parse_call({"type": "function", "function": {"name": "search_catalog", "arguments": '{"query":"Takamine"}'}})
        self.assertEqual(parsed, ("search_catalog", {"query": "Takamine"}))

    def test_schema_rejects_missing_extra_wrong_typed_out_of_range_and_bad_pattern_args(self):
        invalid = (
            ("unknown", {}), ("lookup_public_policy", {}), ("search_catalog", {"unexpected": 1}),
            ("search_catalog", {"page": True}), ("search_catalog", {"page": 21}),
            ("search_catalog", {"payment_method": "cash"}), ("search_catalog", {"max_price_brl": "1.000"}),
            ("get_own_order_status", {"order_id": True}),
        )
        for name, arguments in invalid:
            with self.subTest(name=name, arguments=arguments):
                self.assertFalse(arguments_valid(name, arguments))
        self.assertTrue(arguments_valid("lookup_public_policy", {"query": "horário", "topic": None}))
        self.assertTrue(arguments_valid("get_own_order_status", {"order_id": 4}))

    def test_terminal_rejects_extra_keys_unbounded_text_and_bad_handoff_reason(self):
        invalid = ("not json", "[]", '{"outcome":"answer","text":"x","reason":null,"extra":1}', '{"outcome":"answer","text":"","reason":null}', '{"outcome":"handoff","text":"x","reason":null}', '{"outcome":"answer","text":"x","reason":"customer_request"}', json.dumps({"outcome": "answer", "text": "x" * 2001, "reason": None}))
        for value in invalid:
            with self.subTest(value=value):
                self.assertIsNone(terminal(value))

    def test_result_envelope_keeps_pinned_version_and_counters(self):
        value = result("answer", "Oi", None, [], [], 1, 0, "snapshot-a")
        self.assertEqual((value["model_requests"], value["tool_executions"], value["snapshot_version"]), (1, 0, "snapshot-a"))
