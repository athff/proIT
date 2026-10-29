"""Project-level application views."""

from django.contrib.auth.decorators import login_required
from django.db.models import Count
from django.shortcuts import render

from assets.models import Asset
from dataio.services.authorization import can_export, can_import, can_view
from dataio.services.registry import SPEC_BY_KEY
from people.models import Employee
from vendors.models import Vendor


@login_required
def dashboard(request):
    """Render the authenticated user's operational dashboard."""
    assets = Asset.objects.select_related(
        "model__manufacturer",
        "model__category",
        "assigned_employee",
        "location",
    )
    # One grouped query instead of a COUNT per status.
    counts_by_status = dict(
        Asset.objects.values_list("status").annotate(total=Count("id"))
    )
    status_counts = {
        key: counts_by_status.get(key, 0) for key, _ in Asset.Status.choices
    }
    asset_count = sum(status_counts.values())
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
