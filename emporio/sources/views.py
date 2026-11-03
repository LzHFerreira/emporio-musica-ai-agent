"""Compatibility façade for the protected staff source views."""

from emporio.sources.source_draft_views import (
    source_edit,
    source_preview,
    source_publish,
    source_rollback,
    source_upload,
)
from emporio.sources.source_read_views import source_detail, source_index

__all__ = [
    "source_detail",
    "source_edit",
    "source_index",
    "source_preview",
    "source_publish",
    "source_rollback",
    "source_upload",
]
