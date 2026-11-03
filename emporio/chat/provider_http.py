"""Shared, credential-safe HTTP client construction for direct model providers."""

import httpx


def provider_http_client(client: httpx.Client | None) -> httpx.Client:
    """Use an injected credential-free test client or create a bounded client."""
    if client is not None and (
        client.auth is not None
        or {"authorization", "x-api-key", "api-key"}.intersection(client.headers)
    ):
        raise ValueError("HTTP client must not carry provider credentials")
    return client if client is not None else httpx.Client(timeout=60.0)
