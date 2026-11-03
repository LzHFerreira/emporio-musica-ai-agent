"""Build permission-filtered preview metadata for protected staff pages."""

from emporio.catalog.models import SourceAuditEvent


def preview_context(user, draft, preview) -> dict[str, object]:
    """Expose only preview counts for sources the actor can view."""
    review = _latest_review(user, draft)
    counts = review.counts if review else {}
    visible = _visible_counts(counts, preview)
    return {
        "draft": draft,
        "preview": preview,
        "sources": preview.keys(),
        "counts": visible,
        "requires_deletion_confirmation": _needs_deletion_confirmation(visible),
        "policy_candidate": draft.policy if draft.policy.get("candidate_sha256") else None,
    }


def _latest_review(user, draft):
    return (
        SourceAuditEvent.objects.filter(
            actor=user, draft=draft, event="previewed", revision=draft.revision
        )
        .order_by("-pk")
        .first()
    )


def _visible_counts(counts, preview):
    return {name: counts[name] for name in preview if name in counts}


def _needs_deletion_confirmation(visible):
    return any(item.get("deleted", 0) for item in visible.values())
