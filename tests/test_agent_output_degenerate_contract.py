from emporio.agent_output import output_supported


SOURCES = [{"type": "catalog"}, {"type": "policy"}]
DEGENERATE_REPLIES = [
    "fingerstyle, fingerstyle, fingerstyle, fingerstyle, fingerstyle",
    "análise de devolução: análise de devolução: análise de devolução: análise de devolução:",
    "| | | | | |",
    "Temos ótimas opções de violão para você: 🎸✨",
]


def test_degenerate_model_replies_are_rejected():
    accepted = [t for t in DEGENERATE_REPLIES if output_supported(t, "answer", SOURCES, [])]
    assert accepted == [], f"accepted: {accepted!r}"


def test_normal_greetings_and_offers_remain_supported():
    normal = [
        "Olá! Como posso ajudar?",
        "Oi, oi! Posso ajudar com algo mais?",
        "Posso ajudar: me diga o que procura.",
    ]
    for text in normal:
        assert output_supported(text, "answer", SOURCES, []), f"rejected: {text!r}"
