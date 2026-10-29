"""Assets app models: catalog entities and managed IT assets."""

import uuid
from decimal import Decimal

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


def generate_ticket_reference():
    return f"TKT-{uuid.uuid4().hex[:10].upper()}"


class Category(models.Model):
    """Classification for an asset."""

    name = models.CharField(max_length=120, unique=True)
    description = models.TextField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        verbose_name_plural = "categories"

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        if not self.name.strip():
            raise ValidationError({"name": "Category name cannot be blank."})
        super().clean()


class Manufacturer(models.Model):
    """Manufacturer of an asset model."""

    name = models.CharField(max_length=120, unique=True)
    website = models.URLField(blank=True, null=True)
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]

    def __str__(self) -> str:
        return self.name

    def clean(self) -> None:
        if not self.name.strip():
            raise ValidationError({"name": "Manufacturer name cannot be blank."})
        super().clean()


class AssetModel(models.Model):
    """Manufacturer-specific model name used by assets."""

    name = models.CharField(max_length=120)
    manufacturer = models.ForeignKey(
        Manufacturer,
        on_delete=models.PROTECT,
        related_name="asset_models",
    )
    category = models.ForeignKey(
        Category,
        on_delete=models.PROTECT,
        related_name="asset_models",
    )
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["manufacturer__name", "name"]
        constraints = [
            models.UniqueConstraint(
                fields=["manufacturer", "name"],
                name="unique_manufacturer_asset_model",
            ),
        ]

    def __str__(self) -> str:
        return f"{self.manufacturer} {self.name}"

    def clean(self) -> None:
        if not self.name.strip():
            raise ValidationError({"name": "Asset model name cannot be blank."})
        super().clean()


class Asset(models.Model):
    """A physical or virtual IT asset managed by the organization."""

    class Status(models.TextChoices):
        AVAILABLE = "available", "Available"
        ASSIGNED = "assigned", "Assigned"
        MAINTENANCE = "maintenance", "Maintenance"
        RETIRED = "retired", "Retired"
        LOST = "lost", "Lost"

    asset_tag = models.CharField(max_length=40, unique=True)
    serial_number = models.CharField(max_length=120, unique=True)
    model = models.ForeignKey(
        AssetModel,
        on_delete=models.PROTECT,
        related_name="assets",
    )
    vendor = models.ForeignKey(
        "vendors.Vendor",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
    )
    location = models.ForeignKey(
        "people.Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
    )
    assigned_employee = models.ForeignKey(
        "people.Employee",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assets",
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.AVAILABLE,
    )
    purchase_date = models.DateField(null=True, blank=True)
    purchase_cost = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    warranty_expiry = models.DateField(null=True, blank=True)
    notes = models.TextField(blank=True, null=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["asset_tag"]
        indexes = [
            models.Index(fields=["asset_tag"]),
            models.Index(fields=["serial_number"]),
            models.Index(fields=["status"]),
            models.Index(fields=["assigned_employee"]),
        ]

    def __str__(self) -> str:
        return f"{self.asset_tag}: {self.model}"

    def clean(self) -> None:
        errors = {}
        if not self.asset_tag.strip():
            errors["asset_tag"] = "Asset tag cannot be blank."
        if not self.serial_number.strip():
            errors["serial_number"] = "Serial number cannot be blank."
        if self.purchase_cost is not None and self.purchase_cost < Decimal("0"):
            errors["purchase_cost"] = "Purchase cost cannot be negative."
        if (
            self.purchase_date is not None
            and self.warranty_expiry is not None
            and self.warranty_expiry < self.purchase_date
        ):
            errors["warranty_expiry"] = (
                "Warranty expiry cannot be before the purchase date."
            )
        if errors:
            raise ValidationError(errors)
        super().clean()


class SupportTicket(models.Model):
    """A support request raised against an assigned IT asset."""

    class Priority(models.TextChoices):
        CRITICAL = "critical", "Critical — system unusable (within 1 hour)"
        HIGH = "high", "High — major impact (today)"
        NORMAL = "normal", "Normal — standard issue (next business day)"
        LOW = "low", "Low — minor issue (when available)"

    class Status(models.TextChoices):
        OPEN = "open", "Open"
        IN_PROGRESS = "in_progress", "In progress"
        RESOLVED = "resolved", "Resolved"
        CLOSED = "closed", "Closed"

    reference = models.CharField(
        max_length=24,
        unique=True,
        default=generate_ticket_reference,
        editable=False,
    )
    requester = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        related_name="support_tickets",
    )
    asset = models.ForeignKey(
        Asset,
        on_delete=models.PROTECT,
        related_name="support_tickets",
    )
    description = models.TextField()
    priority = models.CharField(
        max_length=12,
        choices=Priority.choices,
        default=Priority.NORMAL,
    )
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.OPEN,
    )
    assigned_to = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="assigned_support_tickets",
    )
    attachment_data_uri = models.TextField(blank=True)
    attachment_name = models.CharField(max_length=255, blank=True)
    admin_notes = models.TextField(blank=True)
    resolution = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    resolved_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ("-created_at",)
        indexes = (
            models.Index(fields=("status", "priority")),
            models.Index(fields=("requester", "created_at")),
        )

    def __str__(self):
        return f"{self.reference}: {self.asset.asset_tag}"

    def save(self, *args, **kwargs):
        if self.status in {self.Status.RESOLVED, self.Status.CLOSED}:
            self.resolved_at = self.resolved_at or timezone.now()
        else:
            self.resolved_at = None
        super().save(*args, **kwargs)
