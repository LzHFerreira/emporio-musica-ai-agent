import pytest

from emporio.agent_output import output_supported


CATALOG = [{"type": "catalog"}]
POLICY = [{"type": "policy"}]
RETURNS = [{"outcome": "found", "data": [{"text": "frete de devolução por conta da loja"}]}]
TAKAMINE = {"name": "Takamine GD20", "payable_price_brl": "2199.00"}
YAMAHA = {"name": "Yamaha C40", "payable_price_brl": "2999.00"}
YAMAHA_C70 = {"name": "Yamaha C70", "payable_price_brl": "3999.00"}


def catalog_evidence(*products):
    return [{"outcome": "found", "data": list(products)}]


@pytest.mark.parametrize("text", [
    "Você prefere 6 ou 12 cordas?", "Qual faixa de preço você procura?",
    "Você prefere nylon ou aço?",
])
def test_common_clarifications_are_allowed_without_factual_evidence(text):
    assert output_supported(text, "clarification", [], [])


def test_factual_string_count_question_needs_product_evidence():
    assert not output_supported("O violão Yamaha tem 12 cordas?", "answer", CATALOG, catalog_evidence(YAMAHA))


def test_catalog_prices_stay_bound_to_the_correct_product():
    evidence = catalog_evidence(TAKAMINE, YAMAHA)
    assert output_supported("O Takamine GD20 custa R$ 2.199,00.", "answer", CATALOG, evidence)
    assert output_supported("O Yamaha C40 custa R$ 2.999,00.", "answer", CATALOG, evidence)
    assert not output_supported("O Yamaha C40 custa R$ 2.199,00?", "answer", CATALOG, evidence)


def test_same_brand_prices_stay_bound_to_the_exact_model():
    evidence = catalog_evidence(YAMAHA, YAMAHA_C70, TAKAMINE)
    assert output_supported("Yamaha C40 custa R$ 2.999,00.", "answer", CATALOG, evidence)
    assert output_supported("Yamaha C70 custa R$ 3.999,00.", "answer", CATALOG, evidence)
    assert not output_supported("Yamaha C40 custa R$ 3.999,00?", "answer", CATALOG, evidence)
    assert not output_supported("Yamaha C70 custa R$ 2.999,00?", "answer", CATALOG, evidence)


@pytest.mark.parametrize("text, supported", [
    ("Yamaha C70 — R$ 3.999,00.", True),
    ("Yamaha C70 — R$ 2.999,00?", False),
])
def test_product_price_listing_format_stays_bound_to_model(text, supported):
    evidence = catalog_evidence(YAMAHA, YAMAHA_C70)
    assert output_supported(text, "answer", CATALOG, evidence) is supported


def test_both_swapped_multi_product_prices_are_rejected():
    evidence = catalog_evidence(TAKAMINE, YAMAHA)
    assert not output_supported("Takamine custa R$ 2.999 e Yamaha custa R$ 2.199.", "answer", CATALOG, evidence)
    assert output_supported("Takamine custa R$ 2.199 e Yamaha custa R$ 2.999.", "answer", CATALOG, evidence)


def test_wrong_product_price_is_rejected_even_in_a_clarification():
    evidence = catalog_evidence(TAKAMINE, YAMAHA)
    assert not output_supported("Você prefere o Yamaha que custa R$ 2.199,00?", "clarification", CATALOG, evidence)


def test_invented_address_without_any_evidence_is_rejected():
    assert not output_supported("A loja fica na Rua das Palmeiras?", "answer", [], [])


def test_verified_store_address_is_allowed():
    evidence = [{"outcome": "found", "data": [{"text": "Endereço Rua 14 de Maio, 3200 — Centro, Campo Grande - MS, 79202-333"}]}]
    assert output_supported("A loja fica na Rua 14 de Maio, 3200.", "answer", POLICY, evidence)


def test_supported_address_and_hours_can_be_answered_together():
    address = {"outcome": "found", "data": [{"text": "Endereço Rua 14 de Maio, 3200 — Centro, Campo Grande - MS"}]}
    hours = {"outcome": "found", "data": [{"text": "Funcionamento: segunda a sexta-feira, das 09h às 18h"}]}
    assert output_supported("A loja fica na Rua 14 de Maio, 3200 e funciona das 09h às 18h.", "answer", POLICY, [address, hours])


def test_invented_store_address_is_rejected():
    evidence = [{"outcome": "found", "data": [{"text": "Endereço Rua 14 de Maio, 3200 — Centro, Campo Grande - MS, 79202-333"}]}]
    assert not output_supported("A loja fica na Rua das Palmeiras?", "answer", POLICY, evidence)


def test_personal_email_is_rejected():
    assert not output_supported("O cliente usa ana@example.com?", "answer", POLICY, [])


@pytest.mark.parametrize("text", [
    "O frete de devolução fica por conta do cliente.",
    "O cliente paga o frete para devolver o produto.",
])
def test_return_shipping_polarity_must_match_evidence(text):
    assert not output_supported(text, "answer", POLICY, RETURNS)


def test_verified_public_whatsapp_is_allowed():
    contact = [{"outcome": "found", "data": [{"text": "Telefone / WhatsApp (67) 3341-4444"}]}]
    assert output_supported("Nosso WhatsApp é (67) 3341-4444.", "answer", POLICY, contact)


def test_verified_public_email_is_allowed():
    contact = [{"outcome": "found", "data": [{"text": "E-mail contato@empóriodamusica.com.br"}]}]
    assert output_supported("Nosso e-mail é contato@empóriodamusica.com.br.", "answer", POLICY, contact)


def test_exact_unicode_public_email_is_allowed():
    contact = [{"outcome": "found", "data": [{"text": "E-mail contato@empóriodamusica.com.br"}]}]
    assert output_supported("Nosso e-mail é contato@empóriodamusica.com.br.", "answer", POLICY, contact)


def test_accent_stripped_email_lookalike_is_rejected():
    contact = [{"outcome": "found", "data": [{"text": "E-mail contato@empóriodamusica.com.br"}]}]
    assert not output_supported("Nosso e-mail é contato@emporiodamusica.com.br.", "answer", POLICY, contact)


def test_email_from_unrelated_policy_text_is_rejected():
    unrelated = [{"outcome": "found", "data": [{"text": "Atendimento das 09h às 18h"}]}]
    assert not output_supported("Nosso e-mail é contato@empóriodamusica.com.br.", "answer", POLICY, unrelated)


def test_email_evidence_without_reviewed_policy_source_is_rejected():
    email = [{"outcome": "found", "data": [{"text": "contato@empóriodamusica.com.br"}]}]
    assert not output_supported("Nosso e-mail é contato@empóriodamusica.com.br.", "answer", CATALOG, email)


@pytest.mark.parametrize("text", [
    "Posso ajudar com instrumentos, preços e dúvidas sobre a loja. O que gostaria de saber?",
    "Sou o assistente do Empório da Música. Posso ajudar com informações sobre guitarras e violões.",
])
def test_scope_redirect_does_not_need_catalog_evidence(text):
    assert output_supported(text, "answer", [], [])


def test_scope_redirect_guard_still_requires_evidence_for_catalog_facts():
    assert not output_supported("O Yamaha custa R$ 2.999 e está disponível.", "answer", [], [])

@pytest.mark.parametrize("text, outcome, sources, evidence", [
    ("A garantia é de 7 dias.", "answer", POLICY, [{"outcome": "found", "data": [{"text": "Devolução em até 7 dias corridos."}]}]),
    ("O frete de devolução não é pago pela loja.", "answer", POLICY, RETURNS),
    ("Você prefere o Takamine GD20 — R$ 1,00?", "clarification", [], []),
    ("Você prefere garantia vitalícia ou troca grátis?", "clarification", [], []),
])
def test_unsupported_output_claims_are_rejected(text, outcome, sources, evidence):
    assert not output_supported(text, outcome, sources, evidence)


def test_warranty_days_supported_by_warranty_evidence_are_allowed():
    evidence = [{"outcome": "found", "data": [{"text": "Garantia legal de 90 dias para produtos duráveis."}]}]
    assert output_supported("A garantia é de 90 dias.", "answer", POLICY, evidence)


def test_store_address_answer_starting_with_rua_is_supported():
    evidence = [{"outcome": "found", "data": [{"text": "Endereço Rua 14 de Maio, 3200 — Centro, Campo Grande - MS, 79202-333 Telefone / WhatsApp (67) 3341-4444"}]}]
    text = "O endereço da nossa loja é: Rua 14 de Maio, 3200 — Centro, Campo Grande - MS, 79202-333."
    assert output_supported(text, "answer", POLICY, evidence)
