"""SQLite models derived from canonical customer and order CSV files."""

from django.db import models

from emporio.catalog.models import Product, SourceSnapshot


class Customer(models.Model):
    """A customer source row scoped to its CSV snapshot."""

    snapshot = models.ForeignKey(SourceSnapshot, on_delete=models.PROTECT)
    source_id = models.PositiveIntegerField()
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=40, blank=True)
    email = models.EmailField(blank=True)
    city = models.CharField(max_length=120, blank=True)

    class Meta:
        """Enforce customer source identity within each snapshot."""

        constraints = [
            models.UniqueConstraint(
                fields=["snapshot", "source_id"], name="customer_snapshot_source_id"
            )
        ]


class Order(models.Model):
    """A historical order row; no public access service is provided."""

    snapshot = models.ForeignKey(SourceSnapshot, on_delete=models.PROTECT)
    source_id = models.PositiveIntegerField()
    customer = models.ForeignKey(Customer, on_delete=models.PROTECT)
    order_date = models.DateField()
    status = models.CharField(max_length=40)
    total_cents = models.PositiveBigIntegerField()
    payment_method = models.CharField(max_length=40)
    tracking_code = models.CharField(max_length=100, blank=True)
    estimated_delivery = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True)

    class Meta:
        """Enforce order source identity within each snapshot."""

        constraints = [
            models.UniqueConstraint(
                fields=["snapshot", "source_id"], name="order_snapshot_source_id"
            )
        ]


class OrderItem(models.Model):
    """A quantity link between one snapshot order and product."""

    snapshot = models.ForeignKey(SourceSnapshot, on_delete=models.PROTECT)
    order = models.ForeignKey(Order, on_delete=models.PROTECT)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    quantity = models.PositiveIntegerField()

    class Meta:
        """Enforce unique order/product source pairs."""

        constraints = [
            models.UniqueConstraint(fields=["order", "product"], name="order_item_order_product")
        ]
