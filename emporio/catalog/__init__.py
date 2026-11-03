"""Public catalog API."""


def search_catalog(*, snapshot_version=None, **arguments):
    """Search the active catalog using the public bounded projection."""
    from emporio.catalog.services import search_catalog as search

    return search(snapshot_version=snapshot_version, **arguments)


__all__ = ["search_catalog"]
