"""Read-only staff source index and active snapshot tables."""

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.views import redirect_to_login
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.http import HttpRequest, HttpResponse, HttpResponseForbidden
from django.middleware.csrf import get_token
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from emporio.catalog.models import SourceSnapshot
from emporio.sources.draft_data import IDENTITY, MODEL_PERMISSIONS, staff_user
from emporio.sources.read import CSV_FILES, CSV_HEADERS
from emporio.sources.source_tables import source_rows
from emporio.sources.source_web import SOURCE_NAMES, _permission, _source


def source_index(request: HttpRequest) -> HttpResponse:
    """Render the staff source landing page in Portuguese."""
    if not request.user.is_authenticated:
        return redirect_to_login(request.get_full_path())
    user = _index_user(request)
    if isinstance(user, HttpResponse):
        return user
    return render(request, "sources/index.html", _index_context(user))


def _index_user(request: HttpRequest) -> AbstractUser | HttpResponse:
    try:
        return staff_user(request.user)
    except PermissionDenied:
        return HttpResponseForbidden()


def _index_context(user: AbstractUser) -> dict[str, object]:
    active = SourceSnapshot.objects.filter(is_active=True).first()
    return {
        "titulo": "Fontes de dados",
        "sources": _source_entries(user),
        "rollback_versions": _rollback_versions(user, active),
        "active_version": active.version if active else "",
    }


def _source_entries(user: AbstractUser) -> tuple[dict[str, str | tuple[str, ...] | bool], ...]:
    entries: tuple[dict[str, str | tuple[str, ...] | bool], ...] = tuple(
        {
            "name": name,
            "label": SOURCE_NAMES[name],
            "filename": filename,
            "headers": CSV_HEADERS[name],
            "visible": user.has_perm(f"catalog.view_{name}")
            or user.has_perm(f"catalog.view_{MODEL_PERMISSIONS[name]}"),
        }
        for name, filename in CSV_FILES.items()
    )
    return entries + (
        {
            "name": "policy_pdf",
            "label": SOURCE_NAMES["policy_pdf"],
            "filename": "políticas_da_loja.pdf",
            "headers": (),
            "visible": user.has_perm("catalog.view_policy_pdf")
            and user.has_perm("catalog.edit_policy_pdf"),
        },
    )


def _rollback_versions(user: AbstractUser, active: SourceSnapshot | None):
    if active is None or not user.has_perm("catalog.rollback_sources"):
        return ()
    return SourceSnapshot.objects.filter(is_active=False).order_by("-created_at")


@require_http_methods(["GET"])
def source_detail(request: HttpRequest, source: str) -> HttpResponse:
    """Show one searchable, paginated source from the active validated bundle."""
    source = _source(source)
    if source == "policy_pdf":
        return redirect("staff-source-upload", source=source)
    user = _detail_user(request, source)
    if isinstance(user, HttpResponse):
        return user
    snapshot = SourceSnapshot.objects.get(is_active=True)
    return render(
        request,
        "sources/detail.html",
        _detail_context(request, source, user, snapshot),
    )


def _detail_user(request: HttpRequest, source: str) -> AbstractUser | HttpResponse:
    try:
        return _permission(request, "view", source)
    except PermissionDenied:
        if not request.user.is_authenticated:
            return redirect_to_login(request.get_full_path())
        return HttpResponseForbidden()


def _detail_context(
    request: HttpRequest, source: str, user: AbstractUser, snapshot: SourceSnapshot
) -> dict[str, object]:
    rows = source_rows(snapshot, source)
    query = request.GET.get("q", "").strip()[:200]
    get_token(request)
    rows = _filter_rows(rows, query)
    table_rows = _table_rows(source, rows)
    page = Paginator(table_rows, 25).get_page(request.GET.get("page"))
    return {
        "source": source,
        "label": SOURCE_NAMES[source],
        "headers": CSV_HEADERS[source],
        "rows": page,
        "snapshot": snapshot,
        "query": query,
        "can_edit": _can_edit(user, source),
        "can_publish": user.has_perm(f"catalog.publish_{source}"),
    }


def _filter_rows(rows: list[dict[str, str]], query: str) -> list[dict[str, str]]:
    if not query:
        return rows
    needle = query.casefold()
    return [row for row in rows if any(needle in value.casefold() for value in row.values())]


def _table_rows(source: str, rows: list[dict[str, str]]) -> list[dict[str, object]]:
    return [
        {
            "cells": [row.get(header, "") for header in CSV_HEADERS[source]],
            "identity": "|".join(str(row[key]) for key in IDENTITY[source]),
        }
        for row in rows
    ]


def _can_edit(user: AbstractUser, source: str) -> bool:
    return user.has_perm(f"catalog.edit_{source}") or user.has_perm(
        f"catalog.change_{MODEL_PERMISSIONS[source]}"
    )
