"""Assets app admin configuration."""

from django.contrib import admin

from .models import Asset, AssetModel, Category, Manufacturer, SupportTicket


@admin.register(SupportTicket)
class SupportTicketAdmin(admin.ModelAdmin):
    list_display = ("reference", "asset", "requester", "priority", "status", "assigned_to", "created_at")
    list_filter = ("status", "priority", "created_at")
    search_fields = ("reference", "asset__asset_tag", "asset__serial_number", "requester__username", "description")
    readonly_fields = ("reference", "attachment_data_uri", "attachment_name", "created_at", "updated_at", "resolved_at")


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name", "description")
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(Manufacturer)
class ManufacturerAdmin(admin.ModelAdmin):
    list_display = ("name", "is_active", "created_at")
    list_filter = ("is_active",)
    search_fields = ("name",)
    ordering = ("name",)
    readonly_fields = ("created_at", "updated_at")


@admin.register(AssetModel)
class AssetModelAdmin(admin.ModelAdmin):
    list_display = ("name", "manufacturer", "category", "is_active")
    list_filter = ("manufacturer", "category", "is_active")
    search_fields = ("name", "manufacturer__name", "category__name")
    ordering = ("manufacturer__name", "name")
    readonly_fields = ("created_at", "updated_at")


@admin.register(Asset)
class AssetAdmin(admin.ModelAdmin):
    list_display = (
        "asset_tag",
        "serial_number",
        "model",
        "status",
        "assigned_employee",
        "location",
    )
    list_filter = ("status", "model__manufacturer", "model__category")
    search_fields = (
        "asset_tag",
        "serial_number",
        "model__name",
        "model__manufacturer__name",
        "assigned_employee__first_name",
        "assigned_employee__last_name",
    )
    ordering = ("asset_tag",)
    readonly_fields = ("created_at", "updated_at")
