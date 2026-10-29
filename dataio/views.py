"""Staff-protected CSV import, export, and template views."""

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404, HttpRequest, JsonResponse
from django.shortcuts import render
from django.views.decorators.csrf import csrf_protect
from django.views.decorators.http import require_GET, require_POST

from .services.csv_base import CSVImportError
from .services.authorization import can_export, can_import
from .services.export_service import export_response, template_response
from .services.import_service import import_csv
from .services.registry import SPEC_BY_KEY


def _spec_or_404(key: str):
    """Return the spec for a model key, or 404 for an unknown key."""
    try:
        return SPEC_BY_KEY[key]
    except KeyError:
        raise Http404(f"Unknown model key: {key}")


def _allowed(request: HttpRequest, key: str, action: str):
    if not request.user.is_authenticated:
        raise PermissionDenied
    model = _spec_or_404(key).model
    allowed = can_export(request.user, model) if action == "view" else can_import(request.user, model)
    if not allowed:
        raise PermissionDenied


@require_GET
@login_required
def export_csv(request: HttpRequest, model_key: str):
    _allowed(request, model_key, "view")
    return export_response(_spec_or_404(model_key))


@require_GET
@login_required
def template_csv(request: HttpRequest, model_key: str):
    _allowed(request, model_key, "view")
    return template_response(_spec_or_404(model_key))


@require_POST
@csrf_protect
@login_required
def import_csv_view(request: HttpRequest, model_key: str):
    _allowed(request, model_key, "add")
    upload = request.FILES.get("file")
    max_size = getattr(settings, "DATAIO_MAX_UPLOAD_SIZE", 5 * 1024 * 1024)
    if upload is None:
        return JsonResponse({"errors": [{"message": "A file is required."}]}, status=400)
    if upload.size > max_size:
        return JsonResponse({"errors": [{"message": "Uploaded file exceeds the size limit."}]}, status=413)
    try:
        result = import_csv(upload.read(), model_key)
    except CSVImportError as exc:
        return JsonResponse(
            {"model": model_key, "errors": [error.__dict__ for error in exc.errors], "committed": False},
            status=400,
        )
    return JsonResponse({"model": result.model, "total_rows": result.total_rows, "created": result.created, "committed": True})


@login_required
def workspace(request: HttpRequest):
    """Render the authenticated CSV import/export workspace."""
    export_specs = [
        spec for spec in SPEC_BY_KEY.values() if can_export(request.user, spec.model)
    ]
    import_specs = [
        spec for spec in SPEC_BY_KEY.values() if can_import(request.user, spec.model)
    ]
    def present(spec):
        return {
            "spec": spec,
            "key": spec.key,
            "label": spec.model._meta.verbose_name.title(),
            "plural_label": spec.model._meta.verbose_name_plural.title(),
        }
    return render(
        request,
        "dataio/workspace.html",
        {
            "export_specs": [present(spec) for spec in export_specs],
            "import_specs": [present(spec) for spec in import_specs],
        },
    )
