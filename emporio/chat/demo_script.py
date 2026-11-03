"""Fixed source-grounded scenarios for the explicitly scripted local model."""

import json

from emporio.agent_protocol import HANDOFF_TEXT

CASES = (
    {
        "case": "catalog_only",
        "text": "Quanto custa o Takamine GD20 e ele está disponível?",
        "calls": [("search_catalog", {"query": "Takamine GD20", "mode": "resolve"})],
        "answer": "catalog",
    },
    {
        "case": "policy_only",
        "text": "Qual é o horário de funcionamento?",
        "calls": [
            ("lookup_public_policy", {"query": "horário de funcionamento", "topic": "hours"})
        ],
        "answer": "policy",
    },
    {
        "case": "catalog_and_policy",
        "text": "O Takamine GD20 está disponível e posso devolver se me arrepender?",
        "calls": [
            ("search_catalog", {"query": "Takamine GD20", "mode": "resolve"}),
            (
                "lookup_public_policy",
                {"query": "devolução compra online arrependimento", "topic": "returns"},
            ),
        ],
        "answer": "both",
    },
    {
        "case": "pix_budget",
        "text": "Quero um violão de nylon até R$ 1.000 pagando integralmente por PIX.",
        "calls": [
            (
                "search_catalog",
                {
                    "query": "nylon",
                    "category": "Violões",
                    "max_price_brl": "1000",
                    "payment_method": "pix",
                    "available_only": True,
                },
            ),
            ("lookup_public_policy", {"query": "desconto pix promoções não cumulativas"}),
        ],
        "answer": "pix",
    },
    {
        "case": "human_handoff",
        "text": "Quero falar com uma pessoa do atendimento.",
        "calls": [],
        "answer": "handoff",
    },
)


class ScriptedModelClient:
    """Return fixed tool calls and source-derived terminal text without an LLM."""

    def __init__(self, case):
        """Retain one of the fixed scenarios for this worker interaction."""
        self.case = case

    def __call__(self, messages, _tools):
        """Return the scenario tool calls or its source-grounded terminal JSON."""
        results = _tool_results(messages)
        if not self.case["calls"] or results:
            return _terminal(self.case, results)
        return {
            "tool_calls": [_tool_call(index, call) for index, call in enumerate(self.case["calls"])]
        }


def _tool_results(messages):
    results = []
    for message in messages:
        if message.get("role") == "tool":
            try:
                results.append(json.loads(message["content"]))
            except (KeyError, TypeError, json.JSONDecodeError):
                continue
    return results


def _tool_call(index, call):
    name, arguments = call
    return {
        "id": f"demo-tool-{index + 1}",
        "type": "function",
        "function": {"name": name, "arguments": json.dumps(arguments, ensure_ascii=False)},
    }


def _terminal(case, results):
    kind = case["answer"]
    if kind == "handoff":
        return _handoff()
    answer = {
        "catalog": lambda: _catalog_answer(results[0]),
        "policy": lambda: _policy_text(results),
        "both": lambda: _catalog_answer(results[0]) + " " + _policy_text(results[1:]),
        "pix": lambda: _pix_answer(results[0]) + " " + _policy_text(results[1:]),
    }[kind]()
    return _answer(answer)


def _handoff():
    content = {"outcome": "handoff", "text": HANDOFF_TEXT, "reason": "customer_request"}
    return {"content": json.dumps(content, ensure_ascii=False)}


def _answer(text):
    return {
        "content": json.dumps(
            {"outcome": "answer", "text": text, "reason": None}, ensure_ascii=False
        )
    }


def _catalog_answer(result):
    item = _first_item(result)
    return f"{item['name']} está disponível por R$ {item['base_price_brl'].replace('.', ',')}."


def _pix_answer(result):
    item = _first_item(result)
    amount = item["payable_price_brl"].replace(".", ",")
    return f"Para pagamento integral por PIX, {item['name']} fica em R$ {amount}."


def _first_item(result):
    data = result.get("data", [])
    if result.get("outcome") != "found" or not data:
        raise ValueError("scripted demo requires source-backed catalog evidence")
    return data[0]


def _policy_text(results):
    passages = [item for result in results for item in result.get("data", [])]
    if not passages:
        raise ValueError("scripted demo requires source-backed policy evidence")
    return " ".join(item["text"] for item in passages)
