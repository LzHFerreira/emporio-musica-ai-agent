"""Validate and import the six fixed CSV sources into SQLite."""

from django.core.management.base import BaseCommand, CommandError

from emporio.sources.publish import load_sources
from emporio.sources.read import SourceImportError


class Command(BaseCommand):
    """Load canonical CSV files as one validated active snapshot."""

    help = "Validate and load the six canonical Empório CSV files."

    def add_arguments(self, parser):
        """Register the canonical data directory argument."""
        parser.add_argument("--source-dir", required=True)

    def handle(self, *args, **options):
        """Validate all files before creating or activating database rows."""
        try:
            snapshot = load_sources(options["source_dir"])
        except (OSError, SourceImportError) as error:
            raise CommandError(str(error)) from error
        self.stdout.write(f"Loaded CSV snapshot {snapshot.version}")
