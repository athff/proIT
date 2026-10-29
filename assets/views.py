"""Permission-protected Assets management views."""

import base64
from io import BytesIO

import qrcode
from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.paginator import Paginator
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from dataio.services.authorization import (
    ADMINISTRATOR,
    can_change,
    can_delete,
    can_import,
    can_view,
    is_role,
)
from people.models import Employee, Location

from .forms import AssetAssignmentForm, AssetForm
from .models import Asset, Category


def _require(user, action):
    if not action(user, Asset):
        raise PermissionDenied


def _asset_queryset():
    return Asset.objects.select_related(
        "model__manufacturer",
        "model__category",
        "vendor",
        "location",
        "assigned_employee__department",
    )


def _qr_payload(asset):
    """Return the human-readable identity encoded in an asset label."""
    return "\n".join(
        (
            "PROIT ASSET",
            f"Asset tag: {asset.asset_tag}",
            f"Asset name: {asset.model}",
            f"Serial number: {asset.serial_number}",
        )
    )


def _qr_data_uri(payload):
    """Generate an embeddable PNG QR code without storing a generated file."""
    code = qrcode.QRCode(
        error_correction=qrcode.constants.ERROR_CORRECT_M,
        box_size=10,
        border=4,
    )
    code.add_data(payload)
    code.make(fit=True)
    image = code.make_image(fill_color="black", back_color="white")
    output = BytesIO()
    image.save(output, format="PNG")
    encoded = base64.b64encode(output.getvalue()).decode("ascii")
    return f"data:image/png;base64,{encoded}"


@login_required
def asset_list(request):
    _require(request.user, can_view)
    assets = _asset_queryset()
    query = request.GET.get("q", "").strip()
    status = request.GET.get("status", "")
    category = request.GET.get("category", "")
    location = request.GET.get("location", "")
    assignment = request.GET.get("assignment", "")
    if query:
        assets = assets.filter(
            Q(asset_tag__icontains=query)
            | Q(serial_number__icontains=query)
            | Q(model__name__icontains=query)
            | Q(model__manufacturer__name__icontains=query)
            | Q(location__name__icontains=query)
            | Q(assigned_employee__employee_id__icontains=query)
            | Q(assigned_employee__first_name__icontains=query)
            | Q(assigned_employee__last_name__icontains=query)
        )
    if status in dict(Asset.Status.choices):
        assets = assets.filter(status=status)
    if category.isdigit():
        assets = assets.filter(model__category_id=category)
    if location.isdigit():
        assets = assets.filter(location_id=location)
    if assignment == "assigned":
        assets = assets.filter(assigned_employee__isnull=False)
    elif assignment == "unassigned":
        assets = assets.filter(assigned_employee__isnull=True)
    paginator = Paginator(assets, 10)
    page_obj = paginator.get_page(request.GET.get("page"))
    return render(
        request,
        "assets/list.html",
        {
            "assets": page_obj,
            "page_obj": page_obj,
            "status_choices": Asset.Status.choices,
            "categories": Category.objects.order_by("name"),
            "locations": Location.objects.order_by("name"),
            "filters": {
                "q": query,
                "status": status,
                "category": category,
                "location": location,
                "assignment": assignment,
            },
            "can_create": can_import(request.user, Asset),
            "can_edit": can_change(request.user, Asset),
            "can_remove": can_delete(request.user, Asset),
        },
    )


@login_required
def asset_qr_label(request, pk):
    if not is_role(request.user, ADMINISTRATOR):
        raise PermissionDenied
    asset = get_object_or_404(_asset_queryset(), pk=pk)
    payload = _qr_payload(asset)
    return render(
        request,
        "assets/qr_label.html",
        {
            "asset": asset,
            "qr_payload": payload,
            "qr_data_uri": _qr_data_uri(payload),
        },
    )


@login_required
def asset_detail(request, pk):
    _require(request.user, can_view)
    asset = get_object_or_404(_asset_queryset(), pk=pk)
    return render(
        request,
        "assets/detail.html",
        {
            "asset": asset,
            "can_edit": can_change(request.user, Asset),
            "can_remove": can_delete(request.user, Asset),
            "can_print_label": is_role(request.user, ADMINISTRATOR),
        },
    )


@login_required
def asset_assign(request):
    if not can_change(request.user, Asset):
        raise PermissionDenied
    form = AssetAssignmentForm(
        request.POST or None,
        initial={"asset": request.GET.get("asset")} if request.method == "GET" else None,
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            asset = (
                Asset.objects.select_for_update()
                .select_related("model__manufacturer")
                .get(pk=form.cleaned_data["asset"].pk)
            )
            if (
                asset.assigned_employee_id is not None
                or asset.status != Asset.Status.AVAILABLE
            ):
                form.add_error(
                    "asset",
                    "Only available, unassigned assets can be assigned.",
                )
            else:
                asset.assigned_employee = form.cleaned_data["employee"]
                asset.status = Asset.Status.ASSIGNED
                asset.save()
        if not form.errors:
            messages.success(
                request,
                f"Asset {asset.asset_tag} was assigned to "
                f"{asset.assigned_employee.full_name}.",
            )
            return redirect("assets:detail", pk=asset.pk)
    return render(
        request,
        "assets/assign.html",
        {"form": form, "heading": "Assign asset"},
    )


@login_required
def asset_return(request, pk):
    if not can_change(request.user, Asset):
        raise PermissionDenied
    if request.method != "POST":
        return redirect("assets:detail", pk=pk)
    with transaction.atomic():
        asset = Asset.objects.select_for_update().get(pk=pk)
        if asset.assigned_employee_id is None:
            messages.error(request, f"Asset {asset.asset_tag} is not assigned.")
        else:
            asset.assigned_employee = None
            asset.status = Asset.Status.AVAILABLE
            asset.save()
            messages.success(request, f"Asset {asset.asset_tag} was returned.")
    return redirect("assets:detail", pk=pk)


@login_required
def asset_create(request):
    if not can_import(request.user, Asset):
        raise PermissionDenied
    form = AssetForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        asset = form.save()
        messages.success(request, f"Asset {asset.asset_tag} was created.")
        return redirect("assets:detail", pk=asset.pk)
    return render(request, "assets/form.html", {"form": form, "heading": "Add asset"})


@login_required
def asset_update(request, pk):
    if not can_change(request.user, Asset):
        raise PermissionDenied
    asset = get_object_or_404(Asset, pk=pk)
    form = AssetForm(request.POST or None, instance=asset)
    if request.method == "POST" and form.is_valid():
        asset = form.save()
        messages.success(request, f"Asset {asset.asset_tag} was updated.")
        return redirect("assets:detail", pk=asset.pk)
    return render(
        request,
        "assets/form.html",
        {"form": form, "heading": f"Edit {asset.asset_tag}", "asset": asset},
    )


@login_required
def asset_delete(request, pk):
    if not can_delete(request.user, Asset):
        raise PermissionDenied
    asset = get_object_or_404(Asset, pk=pk)
    if request.method == "POST":
        tag = asset.asset_tag
        asset.delete()
        messages.success(request, f"Asset {tag} was deleted.")
        return redirect("assets:list")
    return render(request, "assets/delete.html", {"asset": asset})
