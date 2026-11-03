"""Run the durable single-worker process until interrupted."""

import time

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from emporio.chat.lease import acquire
from emporio.chat.meta import MetaClient
from emporio.chat.providers import check_model_settings, create_model_client
from emporio.chat.recovery import recover_interrupted
from emporio.chat.worker import process_next


class Command(BaseCommand):
    """Poll durable pending messages and send accepted replies."""

    help = "Run the Empório chat worker"

    def add_arguments(self, parser):
        """Add a one-shot option for supervised local runs."""
        parser.add_argument("--once", action="store_true", help="Process at most one turn")

    def handle(self, *args, **options):
        """Run one worker iteration or poll until interrupted."""
        _check_settings()
        _startup()
        model = create_model_client()
        sender = MetaClient()
        try:
            _run(self, options["once"], model, sender)
        except KeyboardInterrupt:
            return
        finally:
            model.client.close()
            sender.client.close()


def _check_settings() -> None:
    try:
        check_model_settings()
    except ValueError as exc:
        raise CommandError(str(exc)) from exc
    if not settings.META_API_TOKEN:
        raise CommandError("Set META_ACCESS_TOKEN before starting the worker")


def _startup() -> None:
    if not acquire():
        raise CommandError("Another chat worker holds the active lease")
    recover_interrupted()


def _run(command, once, model, sender) -> None:
    while True:
        result = process_next(model_client=model, send_client=sender)
        if result is not None:
            command.stdout.write(f"reply_state={result.state}")
        if once:
            return
        time.sleep(0.25)
