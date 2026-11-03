"""Django application configuration for source-backed catalog tables."""

from django.apps import AppConfig


class CatalogConfig(AppConfig):
    """Register catalog and canonical-source snapshot models."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "emporio.catalog"
