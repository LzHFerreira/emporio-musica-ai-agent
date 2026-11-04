"""Portuguese policy-topic aliases and query-term expansion."""

import re

from emporio.catalog.normalize import normalize_text

_TOPICS = {
    "horario": "hours",
    "horarios": "hours",
    "horas": "hours",
    "domingo": "hours",
    "abrem": "hours",
    "funcionamento": "hours",
    "atendimento": "hours",
    "pagamento": "payment",
    "pagamentos": "payment",
    "payments": "payment",
    "payment": "payment",
    "pagar": "payment",
    "pix": "payment",
    "parcelamento": "payment",
    "parcelado": "payment",
    "devolucao": "returns",
    "devolucoes": "returns",
    "arrependimento": "returns",
    "reembolso": "returns",
    "troca": "returns",
    "trocas": "returns",
    "garantia": "warranty",
    "garantias": "warranty",
    "entrega": "delivery",
    "frete": "delivery",
    "promocao": "promotions",
    "promocoes": "promotions",
    "oferta": "promotions",
    "contato": "contact",
    "onde": "contact",
    "ficam": "contact",
    "endereco": "contact",
    "localizacao": "contact",
    "entregam": "delivery",
    "privacidade": "privacy",
}
PUBLIC_TOPICS = frozenset(_TOPICS.values()) | {"scope"}
_EXPANSIONS = {
    "atende": {"atendimento", "horario"},
    "tarde": {"horario", "atendimento"},
    "falar": {"atendimento"},
    "dividir": {"parcelamento", "pagamento"},
    "parcelar": {"parcelamento", "pagamento"},
    "transferencia": {"pix"},
    "desconto": {"pix"},
    "soma": {"cumulatividade", "cumulativas"},
    "somar": {"cumulatividade", "cumulativas"},
    "online": {"compra", "devolucao"},
    "site": {"compra", "devolucao"},
    "comprei": {"compra", "recebimento"},
    "mudei": {"arrependimento"},
    "ideia": {"arrependimento", "devolucao"},
    "volta": {"devolucao", "reembolso"},
    "pedido": {"recebimento"},
    "chegou": {"recebimento"},
    "coberto": {"garantia"},
    "limites": {"garantia", "danos", "desgaste", "modificacoes", "cobertos"},
    "tempo": {"garantia", "prazo"},
    "instrumento": {"produto"},
    "horas": {"horario", "atendimento"},
    "arrepender": {"arrependimento"},
    "arrependeria": {"arrependimento"},
    "devolver": {"devolucao", "reembolso"},
    "devolva": {"devolucao", "reembolso"},
    "querer": {"devolucao"},
    "fora": {"danos", "desgaste", "modificacoes", "cobertos"},
    "onde": {"endereco"},
    "ficam": {"endereco"},
    "localizacao": {"endereco"},
    "entregam": {"entrega"},
    "centro": {"metropolitana"},
}
STOP_WORDS = set(
    "a as ao aos caso com consultar da das de do dos duvida duvidas e em na nas no nos "
    "o os para por que se um uma gerencia".split()
)


def query_tokens(query):
    """Normalize words and add only reviewed paraphrase terms."""
    tokens = set(re.findall(r"\w+", normalize_text(query))) - STOP_WORDS
    for token in tuple(tokens):
        tokens.update(_EXPANSIONS.get(token, ()))
    return tokens - STOP_WORDS


def query_topics(tokens, topic):
    """Prefer query-detected topics, falling back to a normalized topic hint."""
    detected = {_TOPICS[token] for token in tokens if token in _TOPICS}
    if detected:
        return detected
    if topic:
        normalized = normalize_text(topic)
        return {_TOPICS.get(normalized, normalized)}
    return set()
