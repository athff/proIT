"""Vendors app models: Vendor model."""

from django.core.exceptions import ValidationError
from django.db import models


def validate_company_name(value):
    """Validate that company name is not blank."""
    if not value.strip():
        raise ValidationError("Company name cannot be blank.")


class Vendor(models.Model):
    """Vendor or supplier associated with assets and checkouts."""

    company_name = models.CharField(
        max_length=200,
        unique=True,
        help_text="Name of the vendor company (e.g., Acme Corp).",
    )
    contact_name = models.CharField(
        max_length=100,
        blank=True,
        null=True,
        help_text="Name of the primary contact person.",
    )
    email = models.EmailField(
        max_length=120,
        unique=True,
        blank=True,
        null=True,
        help_text="Vendor's contact email address.",
    )
    phone = models.CharField(
        max_length=30,
        blank=True,
        null=True,
        help_text="Vendor's phone number.",
    )
    website = models.URLField(
        blank=True,
        null=True,
        help_text="Vendor's website URL.",
    )
    address = models.TextField(
        blank=True,
        null=True,
        help_text="Vendor's street address, building, or campus details.",
    )
    notes = models.TextField(
        blank=True,
        null=True,
        help_text="Additional notes about the vendor.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="True if the vendor is active and available for asset assignments.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["company_name"]
        indexes = [
            models.Index(fields=["company_name"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return self.company_name

    def get_absolute_url(self) -> str:
        return f"/vendors/vendors/{self.pk}/"

    def clean(self) -> None:
        """Validate model fields before saving."""
        # Ensure company name is not blank
        if not self.company_name.strip():
            raise ValidationError({"company_name": "Company name cannot be blank."})
        # Email is already validated by EmailField, but ensure it's normalized
        if self.email:
            self.email = self.email.lower().strip()
        super().clean()

    def save(self, *args, **kwargs):
        """Always run full_clean before save to validate fields."""
        self.full_clean()
        super().save(*args, **kwargs)