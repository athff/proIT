"""Permission-protected Vendor management views."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from dataio.services.authorization import can_change, can_delete, can_import, can_view

from .forms import VendorForm
from .models import Vendor


def _allowed(user, action):
    if not action(user, Vendor):
        raise PermissionDenied


def _context(request, **extra):
    return {
        "title": "Vendors",
        "singular": "vendor",
        "can_create": can_import(request.user, Vendor),
        "can_edit": can_change(request.user, Vendor),
        "can_remove": can_delete(request.user, Vendor),
        **extra,
    }


@login_required
def vendor_list(request):
    _allowed(request.user, can_view)
    vendors = Vendor.objects.all()
    query = request.GET.get("q", "").strip()
    active = request.GET.get("active", "")
    if query:
        vendors = vendors.filter(
            Q(company_name__icontains=query)
            | Q(contact_name__icontains=query)
            | Q(email__icontains=query)
            | Q(phone__icontains=query)
            | Q(website__icontains=query)
            | Q(address__icontains=query)
            | Q(notes__icontains=query)
        )
    if active in {"true", "false"}:
        vendors = vendors.filter(is_active=active == "true")
    page_obj = Paginator(vendors, 10).get_page(request.GET.get("page"))
    return render(
        request,
        "vendors/list.html",
        _context(
            request,
            page_obj=page_obj,
            records=page_obj,
            filters={"q": query, "active": active},
        ),
    )


@login_required
def vendor_detail(request, pk):
    _allowed(request.user, can_view)
    vendor = get_object_or_404(Vendor, pk=pk)
    return render(request, "vendors/detail.html", _context(request, record=vendor))


@login_required
def vendor_create(request):
    _allowed(request.user, can_import)
    form = VendorForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        vendor = form.save()
        messages.success(request, f"Vendor {vendor.company_name} was created.")
        return redirect("vendors:detail", pk=vendor.pk)
    return render(
        request,
        "vendors/form.html",
        {"form": form, "title": "Add vendor"},
    )


@login_required
def vendor_update(request, pk):
    _allowed(request.user, can_change)
    vendor = get_object_or_404(Vendor, pk=pk)
    form = VendorForm(request.POST or None, instance=vendor)
    if request.method == "POST" and form.is_valid():
        vendor = form.save()
        messages.success(request, f"Vendor {vendor.company_name} was updated.")
        return redirect("vendors:detail", pk=vendor.pk)
    return render(
        request,
        "vendors/form.html",
        {"form": form, "title": "Edit vendor", "record": vendor},
    )


@login_required
def vendor_delete(request, pk):
    _allowed(request.user, can_delete)
    vendor = get_object_or_404(Vendor, pk=pk)
    if request.method == "POST":
        company_name = vendor.company_name
        vendor.delete()
        messages.success(request, f"Vendor {company_name} was deleted.")
        return redirect("vendors:list")
    return render(request, "vendors/delete.html", {"record": vendor})
