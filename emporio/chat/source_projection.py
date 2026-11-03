"""Keep only public locators in persisted turn evidence."""

from typing import Any


def safe_sources(sources: list[Any]) -> list[dict[str, Any]]:
    """Project model-independent source locators for audit display."""
    allowed = {"type", "label", "page", "section", "bundle_version"}
    return [
        {key: value for key, value in source.items() if key in allowed}
        for source in sources
        if isinstance(source, dict)
    ]
