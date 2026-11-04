"""Contract for live-model fixes: out-of-scope terminals, client errors, rejection text."""

from unittest.mock import Mock

import pytest

from emporio.agent import run_turn
from emporio.agent_protocol import OUT_OF_SCOPE_TEXT, REJECTED_TEXT, terminal

RAW = '{"outcome":"out_of_scope","text":"Não vendemos comida.","reason":"unsupported"}'


def test_out_of_scope_terminal_with_reason_is_accepted():
    """Accept out_of_scope terminals that carry a non-null reason."""
    value = terminal(RAW)
    assert (value["outcome"], value["reason"]) == ("out_of_scope", None)


@pytest.mark.django_db
def test_client_exception_retries_and_returns_out_of_scope_text():
    """Retry after a model client exception and return the fixed out-of-scope text."""
    replies = [ValueError, {"content": '{"outcome":"out_of_scope","text":"x","reason":null}'}]
    model = Mock(side_effect=replies)
    result = run_turn("Vocês vendem pizza?", sender="5567998123456", model_client=model)
    assert (result["text"], result["model_requests"]) == (OUT_OF_SCOPE_TEXT, 2)


def test_rejected_text_tells_model_to_use_tools_or_out_of_scope():
    """Mention out_of_scope in the rejection notice so the model can recover."""
    assert "out_of_scope" in REJECTED_TEXT
