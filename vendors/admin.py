"""Vendors app admin configuration."""

from django.contrib import admin

from .models import Vendor


@admin.register(Vendor)
class VendorAdmin(admin.ModelAdmin):
    """Admin configuration for Vendor model."""

    list_display = ("company_name", "contact_name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("company_name", "contact_name", "email")
    ordering = ("company_name",)
    readonly_fields = ("created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("company_name", "email")}),
        ("Contact Information", {"fields": ("contact_name", "phone", "website")}),
        ("Address & Notes", {"fields": ("address", "notes")}),
        ("Status", {"fields": ("is_active",)}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )