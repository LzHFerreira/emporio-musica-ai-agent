"""Public lexical lookup for reviewed customer-facing store policy."""

from typing import Any

from emporio.policy_lookup import lookup_public_policy as _lookup_public_policy
from emporio.sources.policy_pdf import verify_snapshot_pdf


def lookup_public_policy(
    *, query: str, topic: str | None = None, snapshot_version: str | None = None
) -> dict[str, Any]:
    """Return reviewed public passages with source provenance."""
    return _lookup_public_policy(
        query=query, topic=topic, snapshot_version=snapshot_version, verifier=verify_snapshot_pdf
    )


__all__ = ["lookup_public_policy"]
