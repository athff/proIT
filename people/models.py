"""People app models: Department, Location, Employee."""

from django.core.exceptions import ValidationError
from django.db import models


class Department(models.Model):
    """Organizational department or unit."""

    name = models.CharField(
        max_length=120,
        unique=True,
        help_text="Name of the department (e.g., Engineering, Marketing).",
    )
    description = models.TextField(
        blank=True,
        null=True,
        help_text="Optional description of the department's function.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="True if the department is active and employees can be assigned.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return f"/people/departments/{self.pk}/"

    def clean(self) -> None:
        """Validate model fields before saving."""
        if not self.name.strip():
            raise ValidationError({"name": "Department name cannot be blank."})
        super().clean()

    def save(self, *args, **kwargs):
        """Always run full_clean before save to validate fields."""
        self.full_clean()
        super().save(*args, **kwargs)


class Location(models.Model):
    """Physical or organizational location where employees work."""

    name = models.CharField(
        max_length=120,
        unique=True,
        help_text="Name of the location (e.g., Main Office, Remote, Branch - London).",
    )
    address = models.TextField(
        blank=True,
        null=True,
        help_text="Street address, floor, building, or campus details.",
    )
    city = models.CharField(
        max_length=80,
        blank=True,
        null=True,
        help_text="City for the location.",
    )
    region = models.CharField(
        max_length=80,
        blank=True,
        null=True,
        help_text="State, province, or region.",
    )
    country = models.CharField(
        max_length=80,
        blank=True,
        null=True,
        help_text="Country name.",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="True if the location is active and employees can be assigned.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["name"]
        indexes = [
            models.Index(fields=["name"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return self.name

    def get_absolute_url(self) -> str:
        return f"/people/locations/{self.pk}/"

    def clean(self) -> None:
        """Validate model fields before saving."""
        if not self.name.strip():
            raise ValidationError({"name": "Location name cannot be blank."})
        super().clean()

    def save(self, *args, **kwargs):
        """Always run full_clean before save to validate fields."""
        self.full_clean()
        super().save(*args, **kwargs)


class Employee(models.Model):
    """Employee or staff member associated with assets and checkouts."""

    EMPLOYEE_ID_MAX_LENGTH = 30

    employee_id = models.CharField(
        max_length=EMPLOYEE_ID_MAX_LENGTH,
        unique=True,
        help_text="Unique employee identifier (e.g., EMP-1234).",
    )
    first_name = models.CharField(
        max_length=60,
        help_text="Employee's first name.",
    )
    last_name = models.CharField(
        max_length=60,
        help_text="Employee's last name.",
    )
    email = models.EmailField(
        max_length=120,
        unique=True,
        help_text="Employee's work email address.",
    )
    department = models.ForeignKey(
        "Department",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
        help_text="Department the employee belongs to (optional).",
    )
    location = models.ForeignKey(
        "Location",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="employees",
        help_text="Primary work location (optional).",
    )
    is_active = models.BooleanField(
        default=True,
        help_text="True if the employee record is active.",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["last_name", "first_name"]
        indexes = [
            models.Index(fields=["employee_id"]),
            models.Index(fields=["last_name"]),
            models.Index(fields=["first_name"]),
            models.Index(fields=["email"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self) -> str:
        return f"{self.employee_id}: {self.first_name} {self.last_name}"

    def get_absolute_url(self) -> str:
        return f"/people/employees/{self.pk}/"

    def clean(self) -> None:
        """Validate model fields before saving."""
        # Ensure name fields are not blank
        if not self.first_name.strip():
            raise ValidationError({"first_name": "First name cannot be blank."})
        if not self.last_name.strip():
            raise ValidationError({"last_name": "Last name cannot be blank."})
        # Email is already validated by EmailField, but ensure it's normalized
        self.email = self.email.lower().strip()
        super().clean()

    def save(self, *args, **kwargs):
        """Always run full_clean before save to validate fields."""
        self.full_clean()
        super().save(*args, **kwargs)

    @property
    def full_name(self) -> str:
        """Return the employee's full name."""
        return f"{self.first_name} {self.last_name}".strip()

    @property
    def display_name(self) -> str:
        """Return a formatted display name."""
        return f"{self.employee_id} - {self.full_name}"
