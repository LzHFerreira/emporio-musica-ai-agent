from emporio.agent_availability import availability_bound

NAME = "Yamaha C40 Nylon Natural"
UNKNOWN = [{"name": NAME, "availability": "unknown"}]
UNAVAILABLE = [{"name": NAME, "availability": "temporarily_unavailable"}]


def test_unknown_stock_is_not_stated_unavailable():
    assert availability_bound(f"O {NAME} está sem estoque.", UNKNOWN) is False

def test_truthful_unknown_timing_is_not_rejected():
    assert availability_bound(f"Não temos informação sobre o prazo do {NAME}.", UNAVAILABLE)

def test_unavailable_stock_statement_is_supported():
    assert availability_bound(f"O {NAME} está sem estoque.", UNAVAILABLE)
