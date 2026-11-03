"""Private, versioned file storage for inactive policy PDF candidates."""

import os
from pathlib import Path
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError


def stage_candidate(content: bytes, draft_id: int, revision: int) -> tuple[str, Path]:
    """Write a mode-0600 candidate in protected storage and return its relative path."""
    root = _staging_root()
    relative = Path(".drafts") / f"{draft_id}-{revision}-{uuid4().hex}.pdf"
    target = (root.parent / relative).resolve()
    if target.parent != root:
        raise ValidationError("invalid policy staging path")
    descriptor = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(content)
        stream.flush()
        os.fsync(stream.fileno())
    return relative.as_posix(), target


def candidate_path(policy: dict[str, object]) -> Path:
    """Resolve a staged candidate strictly inside the private draft directory."""
    root = _staging_root()
    path = (root.parent / str(policy.get("candidate_path", ""))).resolve()
    if path.parent != root or not path.is_file():
        raise ValidationError("staged policy PDF is unavailable")
    return path


def remove_candidate(relative: str | None) -> None:
    """Delete one old candidate only when its resolved path stays in draft storage."""
    if not relative:
        return
    root = _staging_root()
    path = (root.parent / relative).resolve()
    if path.parent == root:
        path.unlink(missing_ok=True)


def _staging_root() -> Path:
    root = Path(
        getattr(settings, "EMPORIO_BUNDLE_ROOT", Path(settings.BASE_DIR) / ".source-bundles")
    ).resolve()
    static = Path(
        getattr(settings, "STATIC_ROOT", None) or Path(settings.BASE_DIR) / "static"
    ).resolve()
    if root == static or static in root.parents:
        raise ValidationError("policy staging must be outside static storage")
    target = root / ".drafts"
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    target.chmod(0o700)
    return target
