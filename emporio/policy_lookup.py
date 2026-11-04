"""Bounded lexical lookup and provenance formatting for policy passages."""

from typing import Any

from django.db.utils import DatabaseError

from emporio.catalog.models import SourceSnapshot
from emporio.policy_ranking import rank_passages
from emporio.sources.policy_pdf import verify_snapshot_pdf
from emporio.sources.read import SourceImportError


def lookup_public_policy(
    *, query: str, topic: str | None = None, snapshot_version: str | None = None, verifier=None
) -> dict[str, Any]:
    """Return up to three reviewed public passages with pinned bundle provenance."""
    if not _valid_arguments(query, topic, snapshot_version):
        return _result("error", error="invalid_arguments")
    try:
        return _lookup_active(query, topic, snapshot_version, verifier)
    except (DatabaseError, AttributeError, TypeError, KeyError, SourceImportError, OSError):
        return _result("error", error="source_unavailable")


def read_store_manual(*, snapshot_version: str | None = None, verifier=None) -> dict[str, Any]:
    """Return every reviewed public passage of the active policy manual."""
    try:
        snapshot = _select_snapshot(snapshot_version)
        if snapshot is None:
            return _result("error", error="source_unavailable")
        (verifier or verify_snapshot_pdf)(snapshot)
        policy = snapshot.manifest.get("policy", {})
        items = _public_passages(policy)
    except (DatabaseError, AttributeError, TypeError, KeyError, SourceImportError, OSError):
        return _result("error", error="source_unavailable")
    return _found(snapshot, items)


def _public_passages(policy):
    public = [i for i in policy.get("passages", []) if i.get("audience") == "public"]
    return [i for i in public if _valid_page(i.get("page"), policy.get("page_count", 0))]


def _valid_arguments(query, topic, snapshot_version):
    return _valid_query(query) and _valid_topic(topic) and _valid_snapshot(snapshot_version)


def _valid_query(query):
    return isinstance(query, str) and len(query) <= 500


def _valid_topic(topic):
    return topic is None or isinstance(topic, str) and len(topic) <= 80


def _valid_snapshot(version):
    return version is None or isinstance(version, str) and 0 < len(version) <= 64


def _lookup_active(query, topic, snapshot_version, verifier):
    snapshot = _select_snapshot(snapshot_version)
    if snapshot is None:
        return _result("error", error="source_unavailable")
    (verifier or verify_snapshot_pdf)(snapshot)
    policy = snapshot.manifest.get("policy", {})
    ranked = rank_passages(policy.get("passages", []), query, topic, policy.get("page_count", 0))
    return _found(snapshot, ranked[:3]) if ranked else _result("not_found")


def _select_snapshot(version):
    if version is None:
        return SourceSnapshot.objects.filter(is_active=True).first()
    return SourceSnapshot.objects.filter(version=version).first()


def _found(snapshot, selected):
    data = [_public_record(item) for item in selected]
    sources = [source for item in selected for source in _provenance(snapshot, item)]
    return _result("found", data=data, sources=sources)


def _public_record(item):
    return {key: item[key] for key in ("text", "topic", "page", "section", "conflict")}


def _provenance(snapshot, item):
    page_count = snapshot.manifest.get("policy", {}).get("page_count", 0)
    pages = item.get("pages", [item["page"]])
    valid = _preserve_primary(_valid_locators(pages, page_count), item.get("page"), page_count)
    return [_source_record(snapshot, item, page) for page in valid]


def _valid_locators(pages, page_count):
    if not isinstance(pages, list):
        return []
    return [page for page in pages if _valid_page(page, page_count)]


def _preserve_primary(pages, primary, page_count):
    if not pages and _valid_page(primary, page_count):
        return [primary]
    if len(pages) > 1 and primary == pages[0]:
        return [primary, *pages]
    return pages


def _valid_page(page, page_count):
    return type(page) is int and type(page_count) is int and 1 <= page <= page_count


def _source_record(snapshot, item, page):
    return {
        "type": "policy",
        "label": "Manual de políticas da loja",
        "page": page,
        "section": item["section"],
        "bundle_version": snapshot.version,
    }


def _result(outcome, *, data=None, sources=None, error=None):
    return {
        "outcome": outcome,
        "data": data or [],
        "sources": sources or [],
        "page": None,
        "pagination_restarted": False,
        "has_more": False,
        "error_category": error,
    }
