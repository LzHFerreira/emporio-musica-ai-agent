"""Exercise the local signed webhook, worker, tools and mock Meta callback."""

import json

from django.core.management.base import BaseCommand

from emporio.chat.demo import run_demo


class Command(BaseCommand):
    """Run five reproducible local WhatsApp-style interactions."""

    help = "Run the scripted, loopback-only end-to-end chat demonstration"

    def handle(self, *args, **options):
        """Run the demo and print only redacted interaction metrics."""
        report = run_demo()
        self.stdout.write(json.dumps(report, ensure_ascii=False, indent=2))
