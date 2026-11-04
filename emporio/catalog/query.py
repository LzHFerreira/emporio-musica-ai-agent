"""Build filtered, ranked Django ORM catalog queries."""

import re
from typing import Any

from django.db.models import Case, CharField, F, Func, IntegerField, Q, Value, When
from django.db.models.functions import Cast, Concat, Lower, Replace

from emporio.catalog.models import Product, SourceSnapshot
from emporio.catalog.normalize import normalize_text
from emporio.policy_intents import STOP_WORDS as POLICY_STOP_WORDS

STOP_WORDS = POLICY_STOP_WORDS | set(
    "pra quero ate reais real rs pix boleto credito debito cartao".split()
)
INTERNAL_ID_PATTERN = re.compile(r"(?:[0-9]+|(?:produto|product|id) [0-9]+)")


def catalog_query(snapshot: SourceSnapshot, arguments: dict[str, Any]):
    """Apply text, category, price, availability, and stable ranking in SQLite."""
    query = normalize_text(str(arguments["query"]))
    budget = arguments["price_cents"] is not None
    tokens = [t for t in query.split() if t not in STOP_WORDS and not (budget and t.isdigit())]
    tokens = tokens or query.split()
    products = (
        Product.objects.filter(snapshot=snapshot)
        .select_related("category")
        .prefetch_related("promotions")
    )
    products = products.annotate(effective_cents=_price_field(arguments["payment_method"]))
    products = products.annotate(match_text=_match_text())
    products = products.annotate(match_tier=_match_tier(query, tokens))
    products = _filter_text(products, query, tokens)
    products = _filter_category(products, arguments["category"])
    products = _filter_availability(products, arguments["available_only"])
    products = _filter_budget(products, arguments["price_cents"])
    products = _prefer_exact(products)
    return products.order_by("match_tier", "effective_cents", "normalized_name", "source_id")


def _price_field(payment: str) -> F:
    """Select a trusted materialized cents column for the requested method."""
    field = "pix_payable_cents" if payment == "pix" else "standard_payable_cents"
    return F(field)


def _filter_text(products, query: str, tokens: list[str]):
    """Filter descriptive queries while rejecting internal-key references."""
    if query and _internal_id_reference(tokens):
        return products.none()
    return products.filter(match_tier__lt=4) if query else products


def _prefer_exact(products):
    """Keep name, category, and spec matches when any survive every other filter."""
    exact = products.filter(match_tier__lte=2)
    return exact if exact.exists() else products


def _filter_category(products, category: Any):
    """Apply an exact normalized category name when supplied."""
    if category is not None:
        return products.filter(normalized_category=normalize_text(str(category)))
    return products


def _filter_availability(products, available_only: bool):
    """Limit recommendations to sellable active items when requested."""
    if available_only:
        products = products.annotate(
            stock_storage_type=Func(
                F("stock_quantity"), function="typeof", output_field=CharField()
            )
        )
        return products.filter(status="active", stock_quantity__gt=0, stock_storage_type="integer")
    return products


def _filter_budget(products, price: Any):
    """Apply the selected payable-price ceiling in SQLite before pagination."""
    if price is not None:
        return products.filter(effective_cents__lte=price)
    return products


def _match_tier(query: str, tokens: list[str]):
    """Rank exact names, full name-token matches, and broader text matches."""
    if not query:
        return Value(3, output_field=IntegerField())
    name_match = Q()
    field_match = Q()
    search_match = Q()
    for token in tokens:
        name_match &= _token_filter("normalized_name", token)
        field_match &= _token_filter("match_text", token)
        search_match &= _token_filter("normalized_search_text", token)
    return Case(
        When(normalized_name=query, then=Value(0)),
        When(name_match, then=Value(1)),
        When(field_match, then=Value(2)),
        When(search_match, then=Value(3)),
        default=Value(4),
        output_field=IntegerField(),
    )


def _match_text() -> Concat:
    """Join name, category, and specs for matching, leaving out the description."""
    specs = Lower(Replace(Cast("specs", CharField()), Value('"'), Value(" ")))
    return Concat(F("normalized_name"), Value(" "), F("normalized_category"), Value(" "), specs)


def _token_filter(field: str, token: str) -> Q:
    """Match one normalized word at exact token boundaries."""
    pattern = re.sub(r"ao$", "(ao|oes)", re.sub(r"(?<=\D)(?=\d)", " ?", token))
    return Q(**{f"{field}__regex": rf"(^| ){pattern}s?( |$)"})


def _internal_id_reference(tokens: list[str]) -> bool:
    """Reject numeric-only and explicit internal product identifier queries."""
    return INTERNAL_ID_PATTERN.fullmatch(" ".join(tokens)) is not None
