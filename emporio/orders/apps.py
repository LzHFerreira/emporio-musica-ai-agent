"""Django application configuration for private order source tables."""

from django.apps import AppConfig


class OrdersConfig(AppConfig):
    """Register customer, order, and order-item source models."""

    default_auto_field = "django.db.models.BigAutoField"
    name = "emporio.orders"
