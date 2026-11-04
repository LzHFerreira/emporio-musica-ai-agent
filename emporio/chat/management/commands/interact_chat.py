"""Interact with the configured model provider and local Meta harness."""

from django.core.management.base import BaseCommand, CommandError

from emporio.chat.local_interaction import run_interaction
from emporio.chat.providers import create_model_client


class Command(BaseCommand):
    """Run one supplied message or read messages until /quit."""

    help = "Send evaluator-entered messages through the signed local webhook"

    def add_arguments(self, parser):
        """Accept one explicit evaluator message instead of stdin."""
        parser.add_argument("--message", help="Submit one explicit evaluator question")
        parser.add_argument(
            "--sender",
            help="Customer WhatsApp ID (digits) to act as; defaults to a synthetic sender",
        )

    def handle(self, *args, **options):
        """Run the local integration using the explicitly selected provider."""
        try:
            model = create_model_client()
        except ValueError as exc:
            raise CommandError(str(exc)) from exc
        try:
            messages = _messages(options["message"], self.stdout)
            run_interaction(messages, model, self.stdout, sender=options["sender"])
        finally:
            model.client.close()


def _messages(message, output):
    if message is not None:
        yield message
        return
    yield from _prompt_messages(output)


def _prompt_messages(output):
    output.write("Enter a message; type /quit to finish.")
    while True:
        message = _read_message()
        if message is None or message == "/quit":
            return
        if message.strip():
            yield message


def _read_message():
    try:
        return input("you> ")
    except EOFError:
        return None
