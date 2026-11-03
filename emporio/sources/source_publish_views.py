"""CSRF-protected preview, publish, and rollback request handlers."""

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_http_methods

from emporio.catalog.models import SourceDraft, SourceSnapshot
from emporio.sources import drafts as draft_services
from emporio.sources import policy_pdf_service
from emporio.sources.draft_audit import record_rejected
from emporio.sources.source_preview_context import preview_context
from emporio.sources.source_web import _staff, display_error


@require_http_methods(["GET", "POST"])
def source_preview(request: HttpRequest, draft_id: int) -> HttpResponse:
    """Validate and display only rows the draft author may view."""
    user = _staff_or_response(request)
    if isinstance(user, HttpResponse):
        return user
    draft = get_object_or_404(SourceDraft, pk=draft_id)
    if draft.author.pk != user.pk:
        return HttpResponseForbidden()
    try:
        if request.method == "POST":
            draft_services.preview_draft(user, draft)
            policy_pdf_service.review_policy_pdf(
                user, draft, request.POST, expected_revision=_revision(request, draft)
            )
        preview = draft_services.preview_draft(user, draft)
    except (PermissionDenied, ValidationError, ValueError) as error:
        return _error_response(error, request)
    return render(request, "sources/preview.html", preview_context(user, draft, preview))


@require_http_methods(["POST"])
def source_publish(request: HttpRequest, draft_id: int) -> HttpResponse:
    """Publish the exact reviewed revision with a separate deletion confirmation."""
    user = _staff_or_response(request)
    if isinstance(user, HttpResponse):
        return user
    draft = get_object_or_404(SourceDraft, pk=draft_id)
    try:
        draft_services.publish_draft(
            user,
            draft,
            expected_revision=_revision(request, draft),
            confirm_deletions=request.POST.get("confirm_deletions") == "yes",
        )
    except PermissionDenied:
        return HttpResponseForbidden()
    except (ValidationError, ValueError) as error:
        return _publish_error(request, user, draft, error)
    return redirect("staff-source-index")


def _publish_error(request, user, draft, error):
    if "deletions" not in str(error):
        return _error_response(error, request)
    preview = draft_services.preview_draft(user, draft)
    context = preview_context(user, draft, preview)
    context["error"] = display_error(error)
    return render(request, "sources/preview.html", context, status=400)


@require_http_methods(["POST"])
def source_rollback(request: HttpRequest, version: str) -> HttpResponse:
    """Restore a compatible retained source version through the protected service."""
    user = _staff_or_response(request)
    if isinstance(user, HttpResponse):
        return user
    try:
        active = SourceSnapshot.objects.get(is_active=True)
        draft_services.rollback_sources(
            user,
            version,
            expected_version=request.POST.get("expected_version", active.version),
            reason=request.POST.get("reason", ""),
        )
    except PermissionDenied:
        return HttpResponseForbidden()
    except (ValidationError, ValueError) as error:
        return _error_response(error, request)
    return redirect("staff-source-index")


def _staff_or_response(request):
    try:
        return _staff(request)
    except PermissionDenied:
        if request.method == "POST":
            record_rejected(request.user, None, "", PermissionDenied("staff access required"))
        return (
            redirect_to_login(request.get_full_path())
            if not request.user.is_authenticated
            else HttpResponseForbidden()
        )


def _revision(request, draft):
    raw = request.POST.get("revision")
    try:
        return int(raw) if raw is not None else draft.revision
    except ValueError as error:
        raise ValidationError("invalid draft revision") from error


def _error_response(error, request=None):
    status = 403 if isinstance(error, PermissionDenied) else 400
    return render(request, "sources/error.html", {"message": display_error(error)}, status=status)
