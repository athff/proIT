"""Project-level application views."""

from django.conf import settings
from django.contrib.admin.models import LogEntry
from django.contrib.auth import get_user_model
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import Group
from django.contrib.auth.views import PasswordResetView
from django.core.exceptions import PermissionDenied
from django.db import connection
from django.contrib import messages
from django.shortcuts import redirect, render

from assets.models import Asset, AssetModel, Category, Manufacturer, SupportTicket
from dataio.services.authorization import (
    ADMINISTRATOR,
    can_export,
    can_import,
    can_view,
    is_role,
)
from dataio.services.registry import SPEC_BY_KEY
from people.models import Department, Employee, Location
from vendors.models import Vendor

from .forms import AccountProfileForm, ProITPasswordResetForm


def home(request):
    """Route the site root to the appropriate authentication destination."""
    if request.user.is_authenticated:
        return redirect("dashboard")
    return redirect("login")


@login_required
def profile_account(request):
    """Allow a signed-in user to maintain their account identity and avatar."""
    form = AccountProfileForm(
        request.POST or None,
        request.FILES or None,
        user=request.user,
    )
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Your profile was updated.")
        return redirect("profile-account")
    return render(request, "account/profile.html", {"form": form})


@login_required
def admin_panel(request):
    """Operational administration hub for users in the Administrator role."""
    if not is_role(request.user, ADMINISTRATOR):
        raise PermissionDenied

    User = get_user_model()
    recent_users = User.objects.prefetch_related("groups").order_by("-date_joined")[:6]
    recent_admin_activity = LogEntry.objects.select_related(
        "user", "content_type"
    ).order_by("-action_time")[:6]
    email_backend = settings.MAILERS["default"]["BACKEND"].rsplit(".", 1)[-1]
    return render(
        request,
        "admin_panel.html",
        {
            "user_count": User.objects.count(),
            "active_user_count": User.objects.filter(is_active=True).count(),
            "staff_user_count": User.objects.filter(is_staff=True).count(),
            "role_count": Group.objects.count(),
            "asset_count": Asset.objects.count(),
            "asset_model_count": AssetModel.objects.count(),
            "category_count": Category.objects.count(),
            "manufacturer_count": Manufacturer.objects.count(),
            "department_count": Department.objects.count(),
            "location_count": Location.objects.count(),
            "vendor_count": Vendor.objects.count(),
            "ticket_count": SupportTicket.objects.count(),
            "open_ticket_count": SupportTicket.objects.filter(
                status__in=(SupportTicket.Status.OPEN, SupportTicket.Status.IN_PROGRESS)
            ).count(),
            "recent_users": recent_users,
            "recent_admin_activity": recent_admin_activity,
            "deployment_environment": settings.ENVIRONMENT.title(),
            "database_engine": connection.vendor.title(),
            "email_backend": email_backend,
        },
    )


@login_required
def dashboard(request):
    """Render the authenticated user's operational dashboard."""
    assets = Asset.objects.select_related(
        "model__manufacturer",
        "model__category",
        "assigned_employee",
        "location",
    )
    asset_count = assets.count()
    status_counts = {
        key: assets.filter(status=key).count()
        for key, _ in Asset.Status.choices
    }
    status_rows = [
        {
            "value": key,
            "label": label,
            "count": status_counts[key],
            "percent": round(status_counts[key] / asset_count * 100)
            if asset_count
            else 0,
        }
        for key, label in Asset.Status.choices
    ]
    recent_assets = assets.order_by("-created_at")[:6]
    recent_activity = [
        {
            "label": f"Asset {asset.asset_tag} added",
            "detail": str(asset.model),
            "date": asset.created_at,
            "tone": "blue",
        }
        for asset in recent_assets[:4]
    ]
    export_specs = [
        (key, spec)
        for key, spec in SPEC_BY_KEY.items()
        if can_export(request.user, spec.model)
    ]
    import_specs = [
        (key, spec)
        for key, spec in SPEC_BY_KEY.items()
        if can_import(request.user, spec.model)
    ]
    return render(
        request,
        "dashboard.html",
        {
            "asset_count": asset_count,
            "employee_count": Employee.objects.count(),
            "vendor_count": Vendor.objects.count(),
            "available_count": status_counts[Asset.Status.AVAILABLE],
            "maintenance_count": status_counts[Asset.Status.MAINTENANCE],
            "status_counts": status_counts,
            "status_rows": status_rows,
            "recent_assets": recent_assets,
            "recent_activity": recent_activity,
            "export_specs": export_specs,
            "import_specs": import_specs,
            "can_export_assets": any(key == "assets" for key, _ in export_specs),
            "can_import_assets": any(key == "assets" for key, _ in import_specs),
            "can_view_assets": can_view(request.user, Asset),
            "can_view_employees": can_view(request.user, Employee),
            "can_view_vendors": can_view(request.user, Vendor),
            "user_role": (
                "Administrator"
                if request.user.is_superuser
                else request.user.groups.values_list("name", flat=True).first()
                or "Account"
            ),
        },
    )
class ProITPasswordResetView(PasswordResetView):
    """Custom password reset view that sends branded HTML and plain-text emails."""

    # PasswordResetView delegates delivery to PasswordResetForm. Supplying both
    # template names makes Django build a multipart/alternative message.
    email_template_name = "registration/password_reset_email.txt"
    html_email_template_name = "registration/password_reset_email.html"
    form_class = ProITPasswordResetForm
