"""Shared access and display helpers for staff source pages."""

from datetime import datetime

from django.contrib.auth.models import AbstractUser
from django.core.exceptions import PermissionDenied
from django.http import HttpRequest

from emporio.catalog.models import SourceDraft
from emporio.sources import drafts as draft_services
from emporio.sources.draft_data import IDENTITY, require, staff_user
from emporio.sources.read import CSV_HEADERS

SOURCE_NAMES = {
    "categories": "Categorias",
    "products": "Produtos",
    "promotions": "Promoções",
    "customers": "Clientes",
    "orders": "Pedidos",
    "order_items": "Itens dos pedidos",
    "policy_pdf": "Política da loja (PDF)",
}
_CONTROL_KINDS: tuple[tuple[str, frozenset[str]], ...] = (
    ("boolean", frozenset({"is_active"})),
    ("json", frozenset({"specs"})),
    ("decimal", frozenset({"price_brl", "total_brl", "discount_percent"})),
    (
        "integer",
        frozenset(
            {"stock_quantity", "quantity", "category_id", "customer_id", "product_id", "order_id"}
        ),
    ),
    ("date", frozenset({"created_at", "order_date", "estimated_delivery"})),
)
_ERROR_HINTS: tuple[tuple[bool, tuple[str, ...], str], ...] = (
    (True, ("invalid CSV:",), "Não foi possível interpretar o arquivo CSV enviado."),
    (
        True,
        ("invalid row count or shape:",),
        "O CSV está vazio, excede o limite permitido ou contém linhas inconsistentes.",
    ),
    (
        False,
        ("stale", "active source version"),
        "O rascunho ou a versão ativa mudou. Recarregue e revise antes de continuar.",
    ),
    (False, ("not found",), "O registro selecionado não foi encontrado na versão ativa."),
    (False, ("author", "permission"), "Sua conta não tem autorização para esta operação."),
    (False, ("duplicate", "conflicting"), "O CSV contém identidades duplicadas ou conflitantes."),
    (False, ("unknown", "reference"), "O CSV contém uma referência a um registro inexistente."),
    (
        False,
        ("invalid", "missing", "required"),
        "O CSV contém um valor ausente ou inválido. Revise os campos e tente novamente.",
    ),
)


def _staff(request: HttpRequest) -> AbstractUser:
    if not request.user.is_authenticated:
        raise PermissionDenied("login required")
    return staff_user(request.user)


def _permission(request: HttpRequest, action: str, source: str) -> AbstractUser:
    user = _staff(request)
    require(user, action, source)
    return user


def _source(source: str) -> str:
    if source not in CSV_HEADERS and source != "policy_pdf":
        raise PermissionDenied("unknown source")
    return source


def _session_draft(request: HttpRequest, user: AbstractUser, active_version: str) -> SourceDraft:
    draft_id = request.session.get("source_draft_id")
    draft = (
        SourceDraft.objects.filter(pk=draft_id, author_id=user.pk, status="draft").first()
        if draft_id
        else None
    )
    if draft is None or draft.base_version != active_version:
        draft = draft_services.create_draft(user)
        request.session["source_draft_id"] = draft.pk
        request.session["source_draft_revision"] = draft.revision
    return draft


def _edit_context(
    source: str,
    row: dict[str, str],
    editable: tuple[str, ...],
    draft: SourceDraft,
    error: str = "",
) -> dict[str, object]:
    return {
        "source": source,
        "label": SOURCE_NAMES[source],
        "row": row,
        "editable": editable,
        "controls": _edit_controls(source, row, editable),
        "draft": draft,
        "error": error,
        "identity": "|".join(str(row[k]) for k in IDENTITY[source]),
        "headers": CSV_HEADERS[source],
    }


def _edit_controls(source: str, row: dict[str, str], editable: tuple[str, ...]):
    return [
        {
            "field": field,
            "value": _control_value(field, row[field]),
            "kind": _control_kind(field),
            "required": _is_required(source, field),
            "minimum": "1"
            if field in {"category_id", "customer_id", "product_id", "order_id"}
            else "0",
            "checked": row[field].casefold() in {"1", "true"},
        }
        for field in editable
    ]


def _control_value(field: str, value: str) -> str:
    if field in {"order_date", "estimated_delivery"} and value:
        return datetime.strptime(value, "%m/%d/%Y").date().isoformat()
    return value


def _is_required(source: str, field: str) -> bool:
    optional = {
        "categories": {"description"},
        "customers": {"phone", "email", "city"},
        "orders": {"tracking_code", "estimated_delivery", "notes"},
        "products": {"description"},
    }
    return field not in optional.get(source, set())


def _control_kind(field: str) -> str:
    return next((kind for kind, fields in _CONTROL_KINDS if field in fields), "text")


def display_error(error: Exception) -> str:
    """Convert bounded validation and conflict details into Portuguese UI text."""
    message = str(error)
    if message.startswith("invalid columns:"):
        return _column_error(message)
    return _error_hint(message)


def _error_hint(message: str) -> str:
    for is_prefix, patterns, response in _ERROR_HINTS:
        if _matches_hint(message, is_prefix, patterns):
            return response
    return "Não foi possível concluir a operação. Revise os dados e tente novamente."


def _matches_hint(message: str, is_prefix: bool, patterns: tuple[str, ...]) -> bool:
    return (
        message.startswith(patterns[0])
        if is_prefix
        else any(pattern in message for pattern in patterns)
    )


def _column_error(message: str) -> str:
    filename = message.split(":", 1)[1].strip()
    return f"As colunas do arquivo não correspondem ao esquema esperado: {filename}"
