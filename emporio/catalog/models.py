"""SQLite models derived from canonical catalog CSV files."""

from __future__ import annotations

from typing import TYPE_CHECKING

from django.conf import settings
from django.db import models

if TYPE_CHECKING:
    from django.db.models.manager import Manager


class SourceSnapshot(models.Model):
    """Validated immutable import of the six canonical CSV files."""

    version = models.CharField(max_length=64, unique=True)
    manifest = models.JSONField()
    pricing_rule_version = models.CharField(max_length=40)
    pix_basis_points = models.PositiveSmallIntegerField()
    created_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=False)

    class Meta:
        """Expose protected rollback and per-source deletion capabilities."""

        permissions = tuple(
            [
                (f"delete_{name}", f"Can delete {name} source rows")
                for name in (
                    "categories",
                    "products",
                    "promotions",
                    "customers",
                    "orders",
                    "order_items",
                )
            ]
            + [("view_policy_pdf", "Can view policy PDF source")]
            + [("rollback_sources", "Can roll back source snapshots")]
        )


class SourceDraft(models.Model):
    """Persistent staff workspace based on one immutable source snapshot."""

    author = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    base_version = models.CharField(max_length=64)
    revision = models.PositiveIntegerField(default=0)
    sources = models.JSONField()
    policy = models.JSONField(default=dict)
    status = models.CharField(max_length=16, default="draft")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        """Expose both per-source maintenance capabilities and global publish."""

        permissions = tuple(
            [
                (f"edit_{name}", f"Can edit {name} source")
                for name in (
                    "categories",
                    "products",
                    "promotions",
                    "customers",
                    "orders",
                    "order_items",
                )
            ]
            + [
                (f"publish_{name}", f"Can publish {name} source")
                for name in (
                    "categories",
                    "products",
                    "promotions",
                    "customers",
                    "orders",
                    "order_items",
                )
            ]
            + [
                (f"{action}_policy_pdf", f"Can {verb} policy PDF source")
                for action, verb in (("edit", "edit"), ("publish", "publish"))
            ]
            + [("publish_sources", "Can publish source drafts")]
        )


class SourceAuditEvent(models.Model):
    """Bounded record of draft mutation and publication outcomes."""

    actor = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT)
    draft = models.ForeignKey(SourceDraft, on_delete=models.PROTECT, null=True, blank=True)
    event = models.CharField(max_length=32)
    sources = models.JSONField(default=list)
    base_version = models.CharField(max_length=64, blank=True)
    target_version = models.CharField(max_length=64, blank=True)
    revision = models.PositiveIntegerField(default=0)
    outcome = models.CharField(max_length=32, default="success")
    reason = models.TextField(blank=True)
    counts = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)


class Category(models.Model):
    """A source category within an imported snapshot."""

    snapshot = models.ForeignKey(SourceSnapshot, on_delete=models.PROTECT)
    source_id = models.PositiveIntegerField()
    name = models.CharField(max_length=160)
    description = models.TextField(blank=True)

    class Meta:
        """Enforce category source identity within each snapshot."""

        constraints = [
            models.UniqueConstraint(
                fields=["snapshot", "source_id"], name="category_snapshot_source_id"
            )
        ]


class Product(models.Model):
    """A source product and its validated query-price projection."""

    snapshot = models.ForeignKey(SourceSnapshot, on_delete=models.PROTECT)
    source_id = models.PositiveIntegerField()
    category = models.ForeignKey(Category, on_delete=models.PROTECT)
    name = models.CharField(max_length=240)
    normalized_name = models.CharField(max_length=300)
    normalized_search_text = models.TextField()
    normalized_category = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    base_cents = models.PositiveIntegerField()
    standard_payable_cents = models.PositiveIntegerField()
    pix_payable_cents = models.PositiveIntegerField()
    stock_quantity = models.PositiveIntegerField()
    status = models.CharField(max_length=32)
    specs = models.JSONField(default=dict)
    created_at = models.DateField()
    pricing_state = models.CharField(max_length=24, default="calculated")

    if TYPE_CHECKING:

        @property
        def promotions(self) -> Manager[Promotion]:
            """Return source promotions prefetched with this product."""
            raise NotImplementedError

    class Meta:
        """Enforce product source identity within each snapshot."""

        constraints = [
            models.UniqueConstraint(
                fields=["snapshot", "source_id"], name="product_snapshot_source_id"
            )
        ]


class Promotion(models.Model):
    """A source promotion associated with one product snapshot."""

    snapshot = models.ForeignKey(SourceSnapshot, on_delete=models.PROTECT)
    source_id = models.PositiveIntegerField()
    product = models.ForeignKey(Product, on_delete=models.PROTECT, related_name="promotions")
    discount_basis_points = models.PositiveSmallIntegerField()
    description = models.CharField(max_length=240)
    is_active = models.BooleanField()

    class Meta:
        """Enforce promotion source identity within each snapshot."""

        constraints = [
            models.UniqueConstraint(
                fields=["snapshot", "source_id"], name="promotion_snapshot_source_id"
            )
        ]
