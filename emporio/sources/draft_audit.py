"""Payload-free audit helpers and row-count summaries for draft workflows."""

from django.contrib.auth import get_user_model
from django.core.exceptions import PermissionDenied

from emporio.catalog.models import SourceAuditEvent, SourceDraft
from emporio.sources.draft_data import IDENTITY
from emporio.sources.read import CSV_HEADERS


def record_rejected(user, draft, source, error):
    """Write a bounded rejection record without source values or error text."""
    actor, stored_draft = _rejection_records(user, draft)
    if actor is None:
        return
    SourceAuditEvent.objects.create(
        actor=actor,
        draft=stored_draft,
        event="mutation_rejected",
        sources=_audited_sources(source),
        base_version=_base_version(stored_draft),
        revision=_revision(stored_draft),
        outcome=_rejection_outcome(error),
    )


def _rejection_records(user, draft):
    actor = get_user_model().objects.filter(pk=getattr(user, "pk", None)).first()
    stored_draft = SourceDraft.objects.filter(pk=getattr(draft, "pk", None)).first()
    return actor, stored_draft


def _audited_sources(source):
    return [source] if source in CSV_HEADERS or source == "policy_pdf" else []


def _base_version(draft):
    return draft.base_version if draft else ""


def _revision(draft):
    return draft.revision if draft else 0


def _rejection_outcome(error):
    return "permission_denied" if isinstance(error, PermissionDenied) else "validation_rejected"


def source_counts(sources, base):
    """Count inserted, changed, unchanged, and deleted identities per source."""
    return {name: _count_rows(name, rows, base[name]) for name, rows in sources.items()}


def has_changes(counts):
    """Return whether counts include an effective insert, edit, or delete."""
    return any(counts[name] for name in ("inserted", "changed", "deleted"))


def _count_rows(source, rows, old_rows):
    old, new = _identity_rows(source, old_rows), _identity_rows(source, rows)
    common = old.keys() & new.keys()
    changed = sum(old[key] != new[key] for key in common)
    unchanged = len(common) - changed
    return {
        "inserted": len(new.keys() - old.keys()),
        "changed": changed,
        "unchanged": unchanged,
        "deleted": len(old.keys() - new.keys()),
    }


def _identity_rows(source, rows):
    fields = IDENTITY[source]
    return {tuple(row[field] for field in fields): row for row in rows}
