"""Deterministic ranking of reviewed, public policy evidence."""

from emporio.catalog.normalize import normalize_text
from emporio.policy_intents import PUBLIC_TOPICS, STOP_WORDS, query_tokens, query_topics


def rank_passages(passages, query, topic, page_count):
    """Return valid public passages ranked by intent, lexical evidence and locator."""
    normalized = normalize_text(query)
    if _internal_request(normalized):
        return []
    tokens = query_tokens(normalized)
    wanted = query_topics(tokens, topic)
    return _ordered_matches(passages, tokens, wanted, page_count)


def _ordered_matches(passages, tokens, wanted, page_count):
    rows = _rank_public_items(passages, tokens, wanted, page_count)
    rows = _filter_specific_evidence(_filter_ranked(rows, wanted, tokens), tokens)
    if _is_irrelevant(rows, wanted):
        return []
    rows.sort(key=lambda row: row[:-1])
    return [row[-1] for row in rows]


def _is_irrelevant(rows, wanted):
    return not wanted and bool(rows) and min(row[0] for row in rows) >= -2


def _rank_public_items(passages, tokens, wanted, page_count):
    rows = []
    for item in passages:
        if _unrequested_installment_detail(item, tokens):
            continue
        row = _rank_item(item, tokens, wanted, page_count)
        if row is not None:
            rows.append(row)
    return rows


def _filter_ranked(rows, wanted, tokens):
    return _restrict_intents(_prefer_lexical(rows), wanted, tokens)


def _prefer_lexical(rows):
    if not _has_lexical_topic_match(rows):
        return rows
    return [row for row in rows if _is_lexical(row)]


def _has_lexical_topic_match(rows):
    return any(not row[1] and row[0] < 0 for row in rows)


def _is_lexical(row):
    return row[1] or row[0] < 0


def _restrict_intents(rows, wanted, tokens):
    if not wanted:
        return rows
    rows = _matching_topics(rows, wanted)
    rows = _specific_delivery(rows, wanted, tokens)
    if wanted != {"warranty"}:
        return _keep_close_matches(rows)
    return rows


def _matching_topics(rows, wanted):
    return [row for row in rows if row[-1]["topic"] in wanted]


def _specific_delivery(rows, wanted, tokens):
    if wanted == {"delivery"} and "metropolitana" in tokens:
        return _best_scoring_rows(rows)
    return rows


def _best_scoring_rows(rows):
    if not rows:
        return rows
    best = min(row[0] for row in rows)
    return [row for row in rows if row[0] == best]


def _filter_specific_evidence(rows, tokens):
    if "pix" in tokens and _has_nonstacking_rule(rows):
        return _without_promotion_campaign(rows)
    return rows


def _has_nonstacking_rule(rows):
    return any(row[-1]["section"] == "§6.2" for row in rows)


def _without_promotion_campaign(rows):
    return [row for row in rows if row[-1]["section"] != "§6.1"]


def _keep_close_matches(rows):
    """Trim weak sibling hits while retaining equally useful cross-topic evidence."""
    best = {}
    for row in rows:
        topic = row[-1]["topic"]
        best[topic] = min(best.get(topic, 0), row[0])
    return [row for row in rows if row[0] <= best[row[-1]["topic"]] + 1]


def _internal_request(query):
    return "procedimentos internos" in query or "acesso interno" in query


def _rank_item(item, tokens, intents, page_count):
    if not _is_public_item(item, page_count):
        return None
    text_tokens = set(normalize_text(item["text"]).split()) - STOP_WORDS
    matches = len(tokens & text_tokens)
    topic_match = item["topic"] in intents
    if not topic_match and not matches:
        return None
    return (-matches, not topic_match, item["page"], item["section"], item)


def _is_public_item(item, page_count):
    return (
        isinstance(item, dict)
        and item.get("audience") == "public"
        and _valid_item(item, page_count)
    )


def _unrequested_installment_detail(item, tokens):
    """Keep the card installment subsection out of PIX-only policy answers."""
    installment_terms = {"parcelamento", "parcelar", "parcelas", "juros", "cartao"}
    return (
        isinstance(item, dict)
        and item.get("section") == "§3.1"
        and "pix" in tokens
        and not tokens.intersection(installment_terms)
    )


def _valid_item(item, page_count):
    return _valid_text(item) and _valid_location(item, page_count) and _valid_topic(item)


def _valid_text(item):
    text = item.get("text")
    return isinstance(text, str) and 0 < len(text.strip()) <= 400


def _valid_location(item, page_count):
    return (
        type(item.get("page")) is int
        and 1 <= item["page"] <= page_count
        and isinstance(item.get("section"), str)
        and bool(item["section"].strip())
    )


def _valid_topic(item):
    return item.get("topic") in PUBLIC_TOPICS and type(item.get("conflict")) is bool
