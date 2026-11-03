from emporio.agent_output import output_supported


def test_numeric_support_requires_the_complete_claimed_amount():
    sources = [{"type": "catalog"}]
    evidence = [{"price": "1000.00", "model_code": "AC-39"}]
    assert output_supported("O modelo custa R$ 1.000,00.", "answer", sources, evidence)
    assert not output_supported("O modelo custa R$ 100,00.", "answer", sources, evidence)
    assert not output_supported("O modelo custa R$ 100.", "answer", sources, evidence)


def test_nearby_or_concatenated_evidence_digits_do_not_authorize_a_claim():
    sources = [{"type": "catalog"}]
    evidence = [{"price": 1000, "model_code": "AC-39", "product_id": 101}]
    assert not output_supported("O preço é R$ 101,00.", "answer", sources, evidence)
    assert not output_supported("O produto custa 1001.", "answer", sources, evidence)
