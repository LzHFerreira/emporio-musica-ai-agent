"""Loopback-only HTTP transports for the runnable local chat demonstration."""

import hashlib
import hmac
import json
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from threading import Thread
from typing import cast
from urllib.parse import urlsplit
from uuid import uuid4
from wsgiref.simple_server import WSGIRequestHandler, make_server

import httpx
from django.conf import settings
from django.core.wsgi import get_wsgi_application


class MetaAcceptanceServer:
    """Accept mock Meta send requests on an ephemeral loopback port."""

    def __init__(self):
        """Create an ephemeral local server without opening an external listener."""
        self.run_id = uuid4().hex[:12]
        self.accepted: list[str] = []
        self.server = _MetaServer(("127.0.0.1", 0), _MetaHandler)
        self.server.owner = self
        self.path = f"/{settings.META_API_VERSION}/{settings.META_PHONE_NUMBER_ID}/messages"
        self.thread = Thread(target=self.server.serve_forever, daemon=True)

    @property
    def base_url(self):
        """Return the ephemeral loopback base URL used by MetaClient."""
        return f"http://127.0.0.1:{self.server.server_port}"

    def __enter__(self):
        """Start serving mocked provider acceptances."""
        self.thread.start()
        return self

    def __exit__(self, *_):
        """Stop the server and release its local socket."""
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)


class _QuietWSGIHandler(WSGIRequestHandler):
    """Keep fixture senders and request paths out of demo command output."""

    def log_message(self, format, *args):
        """Suppress sender metadata in the local server log."""
        return


@contextmanager
def webhook_server():
    """Serve Django's real webhook view over an ephemeral loopback HTTP port."""
    with make_server(
        "127.0.0.1", 0, get_wsgi_application(), handler_class=_QuietWSGIHandler
    ) as server:
        thread = Thread(target=server.serve_forever, daemon=True)
        thread.start()
        try:
            yield f"http://127.0.0.1:{server.server_port}"
        finally:
            server.shutdown()
            thread.join(timeout=2)


def signed_post(base_url, payload, secret):
    """POST one signed callback to the local Django webhook and return status."""
    if not _loopback_url(base_url):
        raise ValueError("signed callback target must be a local HTTP endpoint")
    raw = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode()
    signature = hmac.new(secret.encode(), raw, hashlib.sha256).hexdigest()
    response = httpx.post(
        f"{base_url.rstrip('/')}/webhooks/whatsapp",
        content=raw,
        headers={"Content-Type": "application/json", "X-Hub-Signature-256": f"sha256={signature}"},
        timeout=3,
    )
    return response.status_code


def _loopback_url(value):
    try:
        parsed = urlsplit(value)
        return parsed.scheme == "http" and _loopback_host(parsed) and _bare_authority(parsed)
    except (AttributeError, ValueError):
        return False


def _loopback_host(parsed):
    return parsed.hostname == "127.0.0.1" and parsed.port is not None


def _bare_authority(parsed):
    return not any((parsed.username, parsed.password, parsed.path, parsed.query, parsed.fragment))


class _MetaHandler(BaseHTTPRequestHandler):
    """Validate only the local Meta text-send contract."""

    def do_POST(self):
        """Validate a request and return a synthetic acceptance receipt."""
        owner = cast(_MetaServer, self.server).owner
        if owner is None:
            self._respond(500)
            return
        if self.path != owner.path:
            self._respond(404)
        elif self.headers.get("Authorization") != "Bearer local-demo-only":
            self._respond(401)
        else:
            payload = _read_payload(self)
            self._accept(payload, owner)

    def _accept(self, payload, owner):
        if payload is None or not _valid_meta_payload(payload):
            self._respond(400)
            return
        provider_id = f"demo-meta-{owner.run_id}-{len(owner.accepted) + 1}"
        owner.accepted.append(provider_id)
        self._respond(200, {"messages": [{"id": provider_id}]})

    def do_GET(self):
        """Reject unsupported methods without disclosing request metadata."""
        self._respond(404)

    def _respond(self, status, body=None):
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        if body is not None:
            self.wfile.write(json.dumps(body).encode())

    def log_message(self, format, *args):
        """Do not print callback paths or protocol IDs."""
        return


def _read_payload(handler):
    try:
        size = int(handler.headers.get("Content-Length", "-1"))
        if size < 0 or size > 16_384:
            return None
        return json.loads(handler.rfile.read(size))
    except (ValueError, json.JSONDecodeError):
        return None


def _valid_meta_payload(payload):
    if not isinstance(payload, dict) or not _valid_recipient(payload):
        return False
    text = payload.get("text")
    context = payload.get("context")
    return _valid_envelope(payload) and _valid_text(text) and _valid_context(context)


def _valid_envelope(payload):
    return (
        payload.get("messaging_product") == "whatsapp"
        and payload.get("recipient_type") == "individual"
        and payload.get("type") == "text"
    )


def _valid_recipient(payload):
    recipient = payload.get("to")
    return isinstance(recipient, str) and recipient.isdigit() and 8 <= len(recipient) <= 15


def _valid_text(text):
    if not isinstance(text, dict):
        return False
    body = text.get("body")
    return text.get("preview_url") is False and isinstance(body, str) and 1 <= len(body) <= 4096


def _valid_context(context):
    return (
        isinstance(context, dict)
        and isinstance(context.get("message_id"), str)
        and bool(context["message_id"])
    )


class _MetaServer(ThreadingHTTPServer):
    """Carry the local mock's response state for its request handler."""

    owner: "MetaAcceptanceServer | None" = None
