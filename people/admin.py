"""People app admin: Department, Location, Employee registration."""

from django.contrib import admin

from .models import AccountProfile, Department, Employee, Location


@admin.register(AccountProfile)
class AccountProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "updated_at")
    search_fields = ("user__username", "user__email")
    readonly_fields = ("avatar_data_uri", "updated_at")


@admin.register(Department)
class DepartmentAdmin(admin.ModelAdmin):
    """Admin configuration for Department model."""

    list_display = ["name", "is_active", "created_at"]
    list_filter = ["is_active", "created_at"]
    search_fields = ["name", "description"]
    date_hierarchy = "created_at"
    ordering = ["name"]

    fieldsets = (
        (None, {"fields": ("name", "description", "is_active")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    readonly_fields = ["created_at", "updated_at"]


@admin.register(Location)
class LocationAdmin(admin.ModelAdmin):
    """Admin configuration for Location model."""

    list_display = ["name", "city", "country", "is_active"]
    list_filter = ["is_active", "country", "city"]
    search_fields = ["name", "city", "country", "region"]
    date_hierarchy = "created_at"
    ordering = ["name"]

    fieldsets = (
        (None, {"fields": ("name", "address", "city", "region", "country", "is_active")}),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    readonly_fields = ["created_at", "updated_at"]


@admin.register(Employee)
class EmployeeAdmin(admin.ModelAdmin):
    """Admin configuration for Employee model."""

    list_display = [
        "display_name",
        "employee_id",
        "email",
        "is_active",
        "department",
        "location",
    ]
    list_filter = [
        "is_active",
        "department",
        "location",
    ]
    search_fields = [
        "employee_id",
        "first_name",
        "last_name",
        "email",
        "department__name",
        "location__name",
    ]
    date_hierarchy = "created_at"
    ordering = ["last_name", "first_name"]

    fieldsets = (
        (
            None,
            {"fields": ("employee_id", "first_name", "last_name", "email")},
        ),
        (
            "Relationships",
            {"fields": ("department", "location")},
        ),
        (
            "Status",
            {"fields": ("is_active",)},
        ),
        (
            "Timestamps",
            {"fields": ("created_at", "updated_at"), "classes": ("collapse",)},
        ),
    )

    readonly_fields = ["created_at", "updated_at"]

    def display_name(self, obj) -> str:
        """Display formatted employee name in admin list."""
        return obj.display_name

    display_name.short_description = "Employee"
    display_name.admin_order_field = "first_name"

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        """Optimize foreign key querysets for department and location."""
        if db_field.name == "department":
            kwargs["queryset"] = Department.objects.filter(is_active=True)
        if db_field.name == "location":
            kwargs["queryset"] = Location.objects.filter(is_active=True)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
