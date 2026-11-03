"""Protected cell-edit form handler and its typed request helpers."""

from datetime import datetime

from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from emporio.catalog.models import SourceSnapshot
from emporio.sources import drafts as draft_services
from emporio.sources.draft_audit import record_rejected
from emporio.sources.draft_data import IDENTITY
from emporio.sources.read import CSV_HEADERS
from emporio.sources.source_tables import source_rows
from emporio.sources.source_web import (
    _edit_context,
    _permission,
    _session_draft,
    _source,
    display_error,
)


@require_http_methods(["GET", "POST"])
def source_edit(request: HttpRequest, source: str, record_id: str) -> HttpResponse:
    """Authorize, resolve the active row, then render or stage one field."""
    source = _source(source)
    user = _edit_access(request, source)
    if isinstance(user, HttpResponse):
        return user
    snapshot = SourceSnapshot.objects.get(is_active=True)
    identity = tuple(record_id.split("|"))
    result = _resolve_edit_row(request, snapshot, source, identity)
    if isinstance(result, HttpResponse):
        return result
    row = result
    draft = _session_draft(request, user, snapshot.version)
    editable = tuple(field for field in CSV_HEADERS[source] if field not in IDENTITY[source])
    return _edit_response(request, source, identity, row, editable, draft, user)


def _edit_response(request, source, identity, row, editable, draft, user):
    if request.method == "POST":
        return _stage_form(request, source, identity, row, editable, draft, user)
    return render(request, "sources/edit.html", _edit_context(source, row, editable, draft))


def _resolve_edit_row(request, snapshot, source, identity):
    if len(identity) != len(IDENTITY[source]):
        return _bad_edit_request(request, source, "invalid identity", "Identificador inválido")
    row = _find_row(snapshot, source, identity)
    if row is None:
        return _bad_edit_request(request, source, "source row not found", "Registro não encontrado")
    return row


def _bad_edit_request(request, source, reason, message):
    if request.method == "POST":
        record_rejected(request.user, None, source, ValidationError(reason))
    return render(request, "sources/error.html", {"message": message}, status=400)


def _edit_access(request, source):
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


def _find_row(snapshot, source, identity):
    return next(
        (
            row
            for row in source_rows(snapshot, source)
            if all(row[key] == value for key, value in zip(IDENTITY[source], identity, strict=True))
        ),
        None,
    )


def _stage_form(request, source, identity, row, editable, draft, user):
    field = request.POST.get("field", "")
    try:
        value = _form_value(field, request.POST.get("value", "0" if field == "is_active" else ""))
        updated = draft_services.stage_cell(
            user, draft, source, identity, field, value, expected_revision=_revision(request, draft)
        )
    except (PermissionDenied, ValidationError, ValueError) as error:
        if isinstance(error, PermissionDenied):
            return HttpResponseForbidden()
        return render(
            request,
            "sources/edit.html",
            _edit_context(source, row, editable, draft, display_error(error)),
            status=400,
        )
    request.session["source_draft_id"] = updated.pk
    request.session["source_draft_revision"] = updated.revision
    return redirect("staff-source-preview", draft_id=updated.pk)


def _form_value(field, value):
    if field in {"order_date", "estimated_delivery"} and value:
        parsed = datetime.strptime(value, "%Y-%m-%d").date()
        return parsed.strftime("%m/%d/%Y")
    return value


def _revision(request, draft):
    raw = request.POST.get("revision")
    try:
        return int(raw) if raw is not None else draft.revision
    except ValueError as error:
        raise ValidationError("invalid draft revision") from error
