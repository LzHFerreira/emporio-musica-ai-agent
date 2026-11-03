"""Prepare verified managed bundles and activate reviewed draft revisions."""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction

from emporio.catalog.models import SourceDraft, SourceSnapshot
from emporio.sources.draft_audit import has_changes, record_rejected, source_counts
from emporio.sources.draft_bundle import prepare_bundle
from emporio.sources.draft_data import (
    bundle,
    materialize,
    require,
    staff_user,
)
from emporio.sources.publication_audit import (
    _matching_review as _matching_review,
)
from emporio.sources.publication_audit import (
    _record_deletion_confirmation as _record_deletion_confirmation,
)
from emporio.sources.publication_audit import (
    _record_publish as _record_publish,
)
from emporio.sources.publication_audit import (
    _require_deletion_confirmation as _require_deletion_confirmation,
)
from emporio.sources.publish import _activate, _stage_snapshot


def publish_draft(user, draft, *, expected_revision, confirm_deletions=False):
    """Publish one explicitly reviewed revision and audit rejected attempts."""
    try:
        return _publish_draft(user, draft, expected_revision, confirm_deletions)
    except (PermissionDenied, ValidationError, ValueError) as error:
        record_rejected(user, draft, "", error)
        raise


def _publish_draft(user, draft, expected_revision, confirm_deletions):
    """Validate and stage outside locks, then recheck permissions and activate."""
    user = staff_user(user)
    current = SourceDraft.objects.get(pk=draft.pk)
    base, sources, changed = _publication_candidate(
        user, current, expected_revision, confirm_deletions
    )
    if not changed:
        return _publish_noop(user, current, expected_revision, current.sources, confirm_deletions)
    rows, manifest, version = _prepare_staged_snapshot(sources, changed, base, current.policy)
    return _activate_reviewed(
        user,
        current,
        expected_revision,
        changed,
        rows,
        manifest,
        version,
        current.sources,
        confirm_deletions,
    )


def _prepare_staged_snapshot(sources, changed, base, policy=None):
    rows, manifest, version = prepare_bundle(sources, changed, base, policy)
    _stage_snapshot(
        version,
        manifest,
        manifest["pricing_rule_version"],
        manifest["pix_basis_points"],
        rows,
    )
    return rows, manifest, version


def _publication_candidate(user, draft, revision, confirm_deletions):
    _check_draft_owner(draft, user)
    _check_revision(draft, revision)
    base = SourceSnapshot.objects.get(version=draft.base_version)
    sources = materialize(draft)
    counts = source_counts(sources, bundle(base))
    changed = [name for name, item in counts.items() if has_changes(item)]
    candidate = draft.policy
    candidate_hash = candidate.get("candidate_sha256")
    if candidate_hash and candidate_hash != base.manifest["pdf_sha256"]:
        changed.append("policy_pdf")
        _require_policy_review(draft, revision)
    _authorize(user, changed, draft.sources)
    review = _matching_review(user, draft, revision)
    _require_deletion_confirmation(review, confirm_deletions)
    return base, sources, changed


def _require_policy_review(draft, revision):
    review = draft.policy.get("review")
    if (
        not review
        or review.get("pdf_sha256") != draft.policy.get("candidate_sha256")
        or review.get("draft_revision") != revision
        or review.get("unchanged_rules_attested") is not True
    ):
        raise ValidationError("policy PDF replacement requires a current reviewed revision")


def _check_draft_owner(draft, user):
    if draft.author.pk != user.pk or draft.status != "draft":
        raise PermissionDenied("only the author may publish an open draft")


def _check_revision(draft, revision):
    if draft.revision != revision:
        raise ValidationError("stale draft revision")


def _authorize(user, changed, edits):
    _authorize_deletions(user, edits)
    if not changed:
        if not user.has_perm("catalog.publish_sources"):
            raise PermissionDenied("publish permission required")
        return
    for source in changed:
        require(user, "publish", source)
        require(user, "edit", source)
        require(user, "view", source)


def _authorize_deletions(user, edits):
    deleted = {edit["source"] for edit in edits if edit["field"] == "__deleted__"}
    for source in deleted:
        require(user, "delete", source)


def _publish_noop(user, draft, expected_revision, edits, confirm_deletions):
    with transaction.atomic():
        current = SourceDraft.objects.select_for_update().get(pk=draft.pk)
        active = SourceSnapshot.objects.select_for_update().get(is_active=True)
        _check_current(current, active, expected_revision)
        fresh = staff_user(user)
        review = _matching_review(fresh, current, expected_revision)
        _authorize(fresh, [], edits)
        _record_deletion_confirmation(fresh, current, review, confirm_deletions)
        _record_publish(fresh, current, active.version, review.counts)
        return active


def _activate_reviewed(
    user, draft, revision, changed, rows, manifest, version, edits, confirm_deletions
):
    with transaction.atomic():
        current = SourceDraft.objects.select_for_update().get(pk=draft.pk)
        active = SourceSnapshot.objects.select_for_update().get(is_active=True)
        _check_current(current, active, revision)
        fresh = staff_user(user)
        review = _matching_review(fresh, current, revision)
        _authorize(fresh, changed, edits)
        _record_deletion_confirmation(fresh, current, review, confirm_deletions)
        snapshot = _activate(
            version,
            manifest,
            manifest["pricing_rule_version"],
            manifest["pix_basis_points"],
            rows,
        )
        _record_publish(fresh, current, snapshot.version, review.counts)
        return snapshot


def _check_current(draft, active, revision):
    if (
        draft.revision != revision
        or draft.base_version != active.version
        or draft.status != "draft"
    ):
        raise ValidationError("stale draft or active source version")
