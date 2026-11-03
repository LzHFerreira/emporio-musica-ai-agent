"""Public catalog search service backed by the active Django ORM snapshot."""

from typing import Any

from django.db.utils import DatabaseError

from emporio.catalog.arguments import parse_arguments
from emporio.catalog.limits import fit_result
from emporio.catalog.models import SourceSnapshot
from emporio.catalog.projection import project_product
from emporio.catalog.query import catalog_query


def search_catalog(
    *, snapshot_version: str | None = None, **arguments: object
) -> dict[str, object]:
    """Search catalog data with strict inputs and a bounded public projection."""
    if not _valid_snapshot_version(snapshot_version):
        return _result("error", error="invalid_arguments")
    values = parse_arguments(arguments)
    if values is None:
        return _result("error", error="invalid_arguments")
    return _search_snapshot(snapshot_version, values)


def _valid_snapshot_version(version):
    return version is None or isinstance(version, str) and 0 < len(version) <= 64


def _search_snapshot(version, values):
    try:
        snapshot = _select_snapshot(version)
        if snapshot is None:
            return _result("error", error="source_unavailable")
        products = catalog_query(snapshot, values)
        return _project_page(products, snapshot, values)
    except DatabaseError:
        return _result("error", error="source_unavailable")


def _select_snapshot(version):
    if version is None:
        return SourceSnapshot.objects.filter(is_active=True).first()
    return SourceSnapshot.objects.filter(version=version).first()


def _project_page(
    products, snapshot: SourceSnapshot, arguments: dict[str, Any]
) -> dict[str, object]:
    """Apply resolve ambiguity and serve one bounded, already-filtered page."""
    first = products.first()
    if first is None:
        return _result("not_found")
    products, outcome = _resolve_candidates(products, first, arguments["mode"])
    return _serve_page(products, snapshot, arguments, outcome)


def _resolve_candidates(products, first, mode: str) -> tuple[Any, str]:
    """Keep only the best descriptive tier and report unresolved ties."""
    if mode != "resolve":
        return products, "found"
    best = products.filter(match_tier=first.match_tier)
    return (best, "ambiguous") if best.count() > 1 else (best, "found")


def _serve_page(products, snapshot: SourceSnapshot, arguments: dict[str, Any], outcome: str):
    """Project at most five rows and one lookahead row from the filtered query."""
    page = int(arguments["page"])
    offset = (page - 1) * 5
    selected = list(products[offset : offset + 6])
    if not selected:
        return _result("not_found")
    data = [project_product(product, str(arguments["payment_method"])) for product in selected[:5]]
    sources: list[dict[str, Any]] = [
        {
            "type": "catalog",
            "label": "Catálogo de produtos",
            "page": None,
            "section": None,
            "bundle_version": snapshot.version,
        }
    ]
    sources.extend(
        _pricing_sources(selected[:5], str(arguments["payment_method"]), snapshot.version)
    )
    return fit_result(
        _result(outcome, data=data, sources=sources, page=page, has_more=len(selected) > 5)
    )


def _result(
    outcome: str,
    data: list[dict[str, object]] | None = None,
    sources: list[dict[str, object]] | None = None,
    page: int | None = None,
    has_more: bool = False,
    error: str | None = None,
) -> dict[str, object]:
    """Build the exact seven-key tool envelope for every service outcome."""
    return {
        "outcome": outcome,
        "data": [] if data is None else data,
        "sources": [] if sources is None else sources,
        "page": page,
        "pagination_restarted": False,
        "has_more": has_more,
        "error_category": error,
    }


def _pricing_sources(products, payment: str, version: str) -> list[dict[str, Any]]:
    """Add public source locators for reviewed rules used in selected prices."""
    sections = set()
    for product in products:
        if product.pricing_state in {"promotion", "ambiguous"}:
            sections.add((6, "§6.2"))
        elif payment == "pix":
            sections.add((3, "§3"))
    return [
        {
            "type": "policy",
            "label": "Política de preços",
            "page": page,
            "section": section,
            "bundle_version": version,
        }
        for page, section in sorted(sections)
    ]
