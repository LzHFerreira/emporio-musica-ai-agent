"""Permission checks and source data reconstruction for persisted drafts."""

import hashlib
from pathlib import Path
from typing import cast

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.models import AbstractUser
from django.core.exceptions import PermissionDenied

from emporio.catalog.models import SourceSnapshot
from emporio.sources.read import CSV_FILES, CSV_HEADERS, SourceImportError, _parse_csv

IDENTITY: dict[str, tuple[str, ...]] = {
    name: (headers[0],) for name, headers in CSV_HEADERS.items() if name != "order_items"
}
IDENTITY["order_items"] = ("order_id", "product_id")
MODEL_PERMISSIONS: dict[str, str] = {
    "categories": "category",
    "products": "product",
    "promotions": "promotion",
    "customers": "customer",
    "orders": "order",
    "order_items": "orderitem",
}


def staff_user(user) -> AbstractUser:
    """Return the current database user after checking active staff status."""
    if not getattr(user, "is_authenticated", False):
        raise PermissionDenied("active staff access required")
    try:
        current = cast(AbstractUser, get_user_model().objects.get(pk=user.pk))
    except get_user_model().DoesNotExist as error:
        raise PermissionDenied("active staff access required") from error
    if not current.is_active or not current.is_staff:
        raise PermissionDenied("active staff access required")
    return current


def require(user, action, source):
    """Enforce one source-specific staff capability."""
    current = staff_user(user)
    grants = _permission_grants(action, source)
    if not any(current.has_perm(grant) for grant in grants):
        raise PermissionDenied(f"missing {action} permission for {source}")
    return current


def _permission_grants(action, source):
    if source == "policy_pdf":
        return [f"catalog.{action}_policy_pdf"]
    grants = [f"catalog.{action}_{source}"]
    legacy_actions = {"edit": "change", "view": "view", "delete": "delete"}
    if action in legacy_actions:
        grants.append(f"catalog.{legacy_actions[action]}_{MODEL_PERMISSIONS[source]}")
    if action == "publish":
        grants.append("catalog.publish_sources")
    return grants


def bundle(snapshot):
    """Load CSV rows from a retained bundle after checking its manifest hashes."""
    path = _bundle_path(snapshot)
    _verify_bundle_layout(path, snapshot)
    sources = _read_sources(path, snapshot)
    _verify_pdf(path, snapshot)
    return sources


def _bundle_path(snapshot):
    root = Path(
        getattr(settings, "EMPORIO_BUNDLE_ROOT", Path(settings.BASE_DIR) / ".source-bundles")
    )
    path = (root / snapshot.version).resolve()
    if path.parent != root.resolve() or not path.is_dir():
        raise SourceImportError("base source bundle is unavailable")
    return path


def _verify_bundle_layout(path, snapshot):
    expected_files = set(CSV_FILES.values()) | {"políticas_da_loja.pdf"}
    if {item.name for item in path.iterdir()} != expected_files:
        raise SourceImportError("base source bundle schema is incompatible")
    hashes = snapshot.manifest.get("csv_sha256")
    if not isinstance(hashes, dict) or set(hashes) != set(CSV_FILES):
        raise SourceImportError("base source manifest schema is incompatible")


def _verify_pdf(path, snapshot):
    pdf_path = (path / "políticas_da_loja.pdf").resolve()
    if pdf_path.parent != path:
        raise SourceImportError("base source bundle path is invalid")
    pdf = pdf_path.read_bytes()
    if hashlib.sha256(pdf).hexdigest() != snapshot.manifest.get("pdf_sha256"):
        raise SourceImportError("base source policy file failed hash verification")
    policy_hash = snapshot.manifest.get("policy", {}).get("pdf_sha256")
    if policy_hash is not None and policy_hash != snapshot.manifest.get("pdf_sha256"):
        raise SourceImportError("reviewed policy metadata is bound to another PDF")


def _read_sources(path, snapshot):
    result = {}
    hashes = snapshot.manifest["csv_sha256"]
    for source, filename in CSV_FILES.items():
        file_path = (path / filename).resolve()
        if file_path.parent != path:
            raise SourceImportError("base source bundle path is invalid")
        content = file_path.read_bytes()
        expected = hashes[source]
        if hashlib.sha256(content).hexdigest() != expected:
            raise SourceImportError("base source bundle failed hash verification")
        result[source] = _parse_csv(filename, content, CSV_HEADERS[source])
    return result


def materialize(draft):
    """Rebuild the complete candidate dataset from base bundle and cell edits."""
    snapshot = SourceSnapshot.objects.get(version=draft.base_version)
    sources = bundle(snapshot)
    grouped = {}
    for edit in draft.sources:
        key = (edit["source"], tuple(edit["identity"]))
        grouped.setdefault(key, []).append(edit)
    for (source, values), edits in grouped.items():
        _apply_identity_edits(sources[source], source, values, edits)
    return sources


def _apply_identity_edits(rows, source, values, edits):
    identity = dict(zip(IDENTITY[source], values, strict=True))
    matches = _matching_rows(rows, identity)
    _delete_row(rows, matches, edits)
    if edits and edits[0]["field"] == "__deleted__":
        return
    if matches:
        row = matches[0]
    else:
        row = _new_row(source, identity, edits)
        rows.append(row)
    _apply_fields(row, source, edits)


def _apply_fields(row, source, edits):
    for edit in edits:
        if edit["field"] not in CSV_HEADERS[source]:
            raise SourceImportError("invalid draft field")
        row[edit["field"]] = edit["value"]


def _matching_rows(rows, identity):
    matches = [row for row in rows if all(row[key] == val for key, val in identity.items())]
    if len(matches) > 1:
        raise SourceImportError("draft identity is ambiguous")
    return matches


def _delete_row(rows, matches, edits):
    deletes = [edit for edit in edits if edit["field"] == "__deleted__"]
    if deletes:
        if not _valid_delete(deletes, edits, matches):
            raise SourceImportError("invalid draft deletion")
        rows.remove(matches[0])


def _valid_delete(deletes, edits, matches):
    return len(deletes) == 1 and len(edits) == 1 and deletes[0]["value"] == "true" and bool(matches)


def _new_row(source, identity, edits):
    if not edits or edits[0]["field"] == "__deleted__":
        raise SourceImportError("draft identity no longer exists in base source")
    row = {edit["field"]: edit["value"] for edit in edits}
    if not _complete_row(source, identity, row):
        raise SourceImportError("draft insert must supply one complete source row")
    return row


def _complete_row(source, identity, row):
    return set(row) == set(CSV_HEADERS[source]) and all(
        row.get(key) == value for key, value in identity.items()
    )
