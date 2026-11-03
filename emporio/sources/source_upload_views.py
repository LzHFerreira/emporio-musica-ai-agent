"""Protected CSV upload handler and preview rendering."""

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse, HttpResponseBadRequest, HttpResponseForbidden
from django.shortcuts import render
from django.views.decorators.http import require_http_methods

from emporio.catalog.models import SourceSnapshot
from emporio.sources import drafts as draft_services
from emporio.sources.draft_audit import record_rejected
from emporio.sources.policy_pdf import stage_policy_pdf
from emporio.sources.source_preview_context import preview_context
from emporio.sources.source_web import (
    SOURCE_NAMES,
    _permission,
    _session_draft,
    _source,
    display_error,
)


@require_http_methods(["GET", "POST"])
def source_upload(request: HttpRequest, source: str) -> HttpResponse:
    """Authorize the source and handle its upload or upload form."""
    source = _source(source)
    user = _upload_access(request, source)
    if isinstance(user, HttpResponse):
        return user
    snapshot = SourceSnapshot.objects.get(is_active=True)
    draft = _session_draft(request, user, snapshot.version)
    if request.method == "GET":
        return _upload_form(request, source, draft)
    return _upload_post(request, source, draft, user)


def _upload_access(request, source):
    try:
        user = _permission(request, "edit", source)
        _permission(request, "view", source)
        return user
    except PermissionDenied:
        if request.method == "POST":
            record_rejected(request.user, None, source, PermissionDenied("source access denied"))
        return (
            redirect_to_login(request.get_full_path())
            if not request.user.is_authenticated
            else HttpResponseForbidden()
        )


def _upload_form(request, source, draft, error="", status=200):
    return render(
        request,
        "sources/upload.html",
        {
            "source": source,
            "label": SOURCE_NAMES[source],
            "draft": draft,
            "error": error,
            "is_pdf": source == "policy_pdf",
        },
        status=status,
    )


def _upload_post(request, source, draft, user):
    upload = request.FILES.get("file")
    if upload is None:
        return _missing_upload(user, draft, source)
    try:
        updated = _stage_source_upload(request, source, draft, user, upload)
    except PermissionDenied:
        return HttpResponseForbidden()
    except (ValidationError, ValueError) as error:
        return _upload_form(request, source, draft, display_error(error), status=400)
    request.session["source_draft_id"] = updated.pk
    request.session["source_draft_revision"] = updated.revision
    return _uploaded_preview(request, user, source, updated)


def _missing_upload(user, draft, source):
    kind = "PDF" if source == "policy_pdf" else "CSV"
    record_rejected(user, draft, source, ValidationError(f"missing {kind} upload"))
    return HttpResponseBadRequest(f"Envie um arquivo {kind}")


def _stage_source_upload(request, source, draft, user, upload):
    revision = _revision(request, draft)
    if source == "policy_pdf":
        updated = stage_policy_pdf(user, draft, upload, expected_revision=revision)
    else:
        updated = draft_services.stage_upload(
            user,
            draft,
            source,
            upload,
            mode=request.POST.get("mode", "append"),
            expected_revision=revision,
        )
    request.session["source_draft_id"] = updated.pk
    request.session["source_draft_revision"] = updated.revision
    return updated


def _uploaded_preview(request, user, source, draft):
    try:
        preview = draft_services.preview_draft(user, draft)
    except (PermissionDenied, ValidationError, ValueError) as error:
        return _upload_form(
            request,
            source,
            draft,
            display_error(error),
            status=400,
        )
    return render(request, "sources/preview.html", preview_context(user, draft, preview))


def _revision(request, draft):
    raw = request.POST.get("revision")
    try:
        return int(raw) if raw is not None else draft.revision
    except ValueError as error:
        raise ValidationError("invalid draft revision") from error
