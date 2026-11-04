"""Grounding contract for model replies without tool evidence."""

import json

import pytest

from emporio.agent import run_turn
from emporio.agent_output import output_supported

CLARIFICATION = "Nossa garantia é vitalícia. Você prefere violão ou guitarra?"


@pytest.mark.parametrize(
    ("text", "outcome"),
    [
        ("Abrimos aos domingos.", "answer"),
        ("Seu pedido já foi enviado.", "answer"),
        (CLARIFICATION, "clarification"),
    ],
)
def test_ungrounded_claims_without_evidence_are_rejected(text, outcome):
    """Reject factual claims and clarifications that lack evidence."""
    assert output_supported(text, outcome, [], []) is False


@pytest.mark.parametrize(
    ("text", "outcome"),
    [
        ("Você prefere violão ou guitarra?", "clarification"),
        ("Olá! Sou o assistente do Empório da Música. Posso ajudar com algum produto?", "answer"),
    ],
)
def test_scope_questions_and_greetings_stay_supported(text, outcome):
    """Keep greetings and preference questions supported without evidence."""
    assert output_supported(text, outcome, [], []) is True


@pytest.mark.django_db
def test_run_turn_does_not_return_ungrounded_clarification():
    """Ensure run_turn never returns an ungrounded clarification."""
    terminal = {"outcome": "clarification", "text": CLARIFICATION, "reason": None}
    result = run_turn(
        "Vocês têm garantia?",
        sender="5567998123456",
        model_client=lambda m, t: {"content": json.dumps(terminal)},
    )
    assert result["text"] != CLARIFICATION
