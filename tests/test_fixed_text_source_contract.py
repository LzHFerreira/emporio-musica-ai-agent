"""Contract for fixed agent texts: they must match the store manual's scope."""

from emporio.agent_protocol import OUT_OF_SCOPE_TEXT, REJECTED_TEXT, SYSTEM_PROMPT


def test_out_of_scope_text_excludes_accessories():
    """Out-of-scope text says only musical instruments and excludes accessories."""
    assert "acessórios" not in OUT_OF_SCOPE_TEXT
    assert "exclusivamente com instrumentos musicais" in OUT_OF_SCOPE_TEXT


def test_rejected_text_excludes_accessories():
    """Rejection notice does not claim accessories are in scope."""
    assert "acessórios" not in REJECTED_TEXT


def test_system_prompt_does_not_promise_full_manual():
    """System prompt does not promise the full manual is returned by read_store_manual."""
    assert "manual completo" not in SYSTEM_PROMPT
