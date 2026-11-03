"""Django application configuration for chat runtime records."""

from django.apps import AppConfig


class ChatConfig(AppConfig):
    """Register durable customer conversation state."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "emporio.chat"
