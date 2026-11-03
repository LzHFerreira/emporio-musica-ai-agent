"""Bound a blocking model HTTP attempt by total elapsed wall time."""

from queue import Empty, Queue
from threading import Thread
from time import monotonic

import httpx


def post_with_timeout(
    client: httpx.Client,
    url: str,
    *,
    headers: dict[str, str],
    payload: dict[str, object],
    timeout: float,
) -> httpx.Response:
    """Wait only for the remaining budget; late HTTP results cannot run tools."""
    timeout = min(float(timeout), 60.0)
    if not timeout > 0:
        raise httpx.TimeoutException("Model request deadline exhausted")
    deadline = monotonic() + timeout
    result: Queue[httpx.Response | Exception] = Queue(maxsize=1)
    Thread(target=_post, args=(result, client, url, headers, payload, timeout), daemon=True).start()
    try:
        value = result.get(timeout=max(0, deadline - monotonic()))
    except Empty:
        raise httpx.TimeoutException("Model request exceeded its wall-time budget") from None
    if monotonic() > deadline:
        raise httpx.TimeoutException("Model result arrived after its wall-time budget")
    if isinstance(value, Exception):
        raise value
    return value


def _post(
    result: Queue[httpx.Response | Exception],
    client: httpx.Client,
    url: str,
    headers: dict[str, str],
    payload: dict[str, object],
    timeout: float,
) -> None:
    value: httpx.Response | Exception
    try:
        value = client.post(
            url, headers=headers, json=payload, timeout=timeout, follow_redirects=False
        )
    except Exception as error:
        value = error
    result.put(value)
