"""Streaming CSV exports and generated import templates."""

import csv
from itertools import chain

from django.http import StreamingHttpResponse

from .registry import ModelSpec


class Echo:
    def write(self, value):
        return value


def _safe_cell(value) -> str:
    """Neutralize spreadsheet formulas while retaining ordinary CSV values."""
    text = "" if value is None else str(value)
    probe = text
    while probe and (probe[0].isspace() or ord(probe[0]) < 32):
        probe = probe[1:]
    if probe and probe[0] in "=+-@":
        return "'" + text
    return text


def _value(obj, column: str):
    if column == "manufacturer":
        value = (
            obj.manufacturer.name
            if hasattr(obj, "manufacturer")
            else obj.model.manufacturer.name
        )
    elif column == "model":
        value = obj.model.name if hasattr(obj, "model") else obj.name
    elif column == "category":
        value = obj.category.name
    elif column == "department":
        value = obj.department.name if obj.department else ""
    elif column == "location":
        value = obj.location.name if obj.location else ""
    elif column == "vendor":
        value = obj.vendor.company_name if obj.vendor else ""
    elif column == "assigned_employee":
        value = obj.assigned_employee.employee_id if obj.assigned_employee else ""
    else:
        value = getattr(obj, column, "")
    return _safe_cell(
        "" if value is None
        else str(value).lower() if isinstance(value, bool)
        else value
    )


def export_response(spec: ModelSpec) -> StreamingHttpResponse:
    writer = csv.writer(Echo())
    queryset = spec.model.objects.all()
    if spec.select_related:
        queryset = queryset.select_related(*spec.select_related)
    rows = ([_value(obj, column) for column in spec.headers] for obj in queryset.iterator())
    response = StreamingHttpResponse(
        (writer.writerow(row) for row in chain((spec.headers,), rows)),
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="{spec.key}.csv"'
    return response


def template_response(spec: ModelSpec) -> StreamingHttpResponse:
    response = StreamingHttpResponse(
        [",".join(spec.headers) + "\r\n"],
        content_type="text/csv; charset=utf-8",
    )
    response["Content-Disposition"] = f'attachment; filename="{spec.key}_template.csv"'
    return response
