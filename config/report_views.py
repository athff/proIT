"""Database-backed reporting views."""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db.models import Count
from django.shortcuts import render

from assets.models import Asset
from dataio.services.authorization import can_view
@login_required
def reports(request):
    if not can_view(request.user, Asset):
        raise PermissionDenied
    assets = Asset.objects.select_related("model__category", "location")
    total = assets.count()
    status_rows = [
        {
            "label": label,
            "count": assets.filter(status=value).count(),
            "percent": round(assets.filter(status=value).count() / total * 100)
            if total else 0,
        }
        for value, label in Asset.Status.choices
    ]
    category_rows = list(
        assets.values("model__category__name")
        .annotate(count=Count("id"))
        .order_by("-count", "model__category__name")
    )
    location_rows = list(
        assets.values("location__name")
        .annotate(count=Count("id"))
        .order_by("-count", "location__name")
    )
    return render(
        request,
        "reports.html",
        {
            "total": total,
            "status_rows": status_rows,
            "category_rows": category_rows,
            "location_rows": location_rows,
            "assigned_count": assets.filter(assigned_employee__isnull=False).count(),
            "available_count": assets.filter(status=Asset.Status.AVAILABLE).count(),
        },
    )
