"""Permission-protected People management views."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.shortcuts import get_object_or_404, redirect, render

from dataio.services.authorization import can_change, can_delete, can_import, can_view

from .forms import DepartmentForm, EmployeeForm, LocationForm
from .models import Department, Employee, Location

RESOURCE_CONFIG = {
    "employees": {
        "model": Employee, "form": EmployeeForm, "title": "Employees", "singular": "employee",
        "query_fields": ("employee_id", "first_name", "last_name", "email", "department__name", "location__name"),
    },
    "departments": {
        "model": Department, "form": DepartmentForm, "title": "Departments", "singular": "department",
        "query_fields": ("name", "description"),
    },
    "locations": {
        "model": Location, "form": LocationForm, "title": "Locations", "singular": "location",
        "query_fields": ("name", "address", "city", "region", "country"),
    },
}


def _config(resource):
    try:
        return RESOURCE_CONFIG[resource]
    except KeyError:
        raise PermissionDenied


def _allowed(user, action, model):
    if not action(user, model):
        raise PermissionDenied


def _queryset(resource):
    model = _config(resource)["model"]
    return model.objects.select_related("department", "location") if model is Employee else model.objects.all()


def _common_context(request, resource, **extra):
    config = _config(resource)
    return {
        "resource": resource, "title": config["title"], "singular": config["singular"],
        "can_create": can_import(request.user, config["model"]),
        "can_edit": can_change(request.user, config["model"]),
        "can_remove": can_delete(request.user, config["model"]),
        **extra,
    }


@login_required
def people_list(request, resource):
    config = _config(resource)
    _allowed(request.user, can_view, config["model"])
    records = _queryset(resource)
    query = request.GET.get("q", "").strip()
    active = request.GET.get("active", "")
    if query:
        search = Q()
        for field in config["query_fields"]:
            search |= Q(**{f"{field}__icontains": query})
        records = records.filter(search)
    if active in {"true", "false"}:
        records = records.filter(is_active=active == "true")
    page_obj = Paginator(records, 10).get_page(request.GET.get("page"))
    return render(request, "people/list.html", _common_context(
        request, resource, page_obj=page_obj, records=page_obj,
        filters={"q": query, "active": active},
    ))


@login_required
def people_detail(request, resource, pk):
    config = _config(resource)
    _allowed(request.user, can_view, config["model"])
    record = get_object_or_404(_queryset(resource), pk=pk)
    return render(request, "people/detail.html", _common_context(request, resource, record=record))


@login_required
def people_create(request, resource):
    config = _config(resource)
    _allowed(request.user, can_import, config["model"])
    form = config["form"](request.POST or None)
    if request.method == "POST" and form.is_valid():
        record = form.save()
        messages.success(request, f"{config['singular'].capitalize()} {record} was created.")
        return redirect("people:detail", resource=resource, pk=record.pk)
    return render(request, "people/form.html", {"form": form, "title": f"Add {config['singular']}", "resource": resource})


@login_required
def people_update(request, resource, pk):
    config = _config(resource)
    _allowed(request.user, can_change, config["model"])
    record = get_object_or_404(_queryset(resource), pk=pk)
    form = config["form"](request.POST or None, instance=record)
    if request.method == "POST" and form.is_valid():
        record = form.save()
        messages.success(request, f"{config['singular'].capitalize()} {record} was updated.")
        return redirect("people:detail", resource=resource, pk=record.pk)
    return render(request, "people/form.html", {"form": form, "title": f"Edit {config['singular']}", "resource": resource, "record": record})


@login_required
def people_delete(request, resource, pk):
    config = _config(resource)
    _allowed(request.user, can_delete, config["model"])
    record = get_object_or_404(_queryset(resource), pk=pk)
    if request.method == "POST":
        label = str(record)
        record.delete()
        messages.success(request, f"{config['singular'].capitalize()} {label} was deleted.")
        return redirect("people:list", resource=resource)
    return render(request, "people/delete.html", {"resource": resource, "singular": config["singular"], "record": record})
