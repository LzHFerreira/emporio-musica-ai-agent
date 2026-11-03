"""Expose signed WhatsApp webhook verification and ingestion."""

from django.conf import settings
from django.http import HttpRequest, HttpResponse
from django.views.decorators.csrf import csrf_exempt

from emporio.chat.webhook import MAX_BODY, process_envelope, signature_valid


def whatsapp_webhook(request: HttpRequest) -> HttpResponse:
    """Verify GET subscriptions and acknowledge only authenticated callbacks."""
    if request.method == "GET":
        return _verify(request)
    if request.method != "POST":
        return HttpResponse(status=405)
    return _ingest(request)


def _verify(request: HttpRequest) -> HttpResponse:
    mode, token, challenge = _verification_values(request)
    if _verification_missing(mode, token, challenge):
        return HttpResponse(status=400)
    if mode != "subscribe" or token != settings.META_WEBHOOK_VERIFY_TOKEN:
        return HttpResponse(status=403)
    return HttpResponse(challenge, content_type="text/plain")


def _verification_values(request):
    return (
        request.GET.get("hub.mode"),
        request.GET.get("hub.verify_token"),
        request.GET.get("hub.challenge"),
    )


def _verification_missing(mode, token, challenge):
    return not mode or token is None or challenge is None


def _ingest(request: HttpRequest) -> HttpResponse:
    raw = request.body
    if len(raw) > MAX_BODY:
        return HttpResponse(status=413)
    if not signature_valid(raw, request.headers.get("X-Hub-Signature-256")):
        return HttpResponse(status=403)
    return _process_signed(raw)


def _process_signed(raw):
    try:
        process_envelope(raw)
    except ValueError as error:
        return HttpResponse(status=413 if str(error) in {"body_limit", "batch_limit"} else 400)
    except Exception:
        return HttpResponse(status=503)
    return HttpResponse(status=200)


whatsapp_webhook = csrf_exempt(whatsapp_webhook)
