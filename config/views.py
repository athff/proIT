"""Project-level application views."""

from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import PasswordResetView
from django.shortcuts import render

from assets.models import Asset
from dataio.services.authorization import can_export, can_import, can_view
from dataio.services.registry import SPEC_BY_KEY
from people.models import Employee
from vendors.models import Vendor

from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from django.contrib.auth.tokens import default_token_generator
from django.urls import reverse
from django.contrib.auth import get_user_model
from datetime import datetime

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

    def send_mail(self, subject, email_from, to_email, context):
        """Send password reset email with both HTML and plain-text alternatives."""
        # Ensure reset_url is present in the context
        if "reset_url" not in context:
            # The e‑mail that triggered the reset is obtained from the POST data
            # (the form always submits the e‑mail address). Use it to look up the user.
            email = context.get("email") or self.request.POST.get("email")
            if email:
                User = get_user_model()
                try:
                    user = User.objects.get(email=email)
                except User.DoesNotExist:
                    user = None
                if user:
                    uidb64 = urlsafe_base64_encode(force_bytes(user.pk)).decode()
                    token = default_token_generator.make_token(user)
                    rel_url = reverse("password_reset_confirm", kwargs={"uidb64": uidb64, "token": token})
                    scheme = self.request.scheme
                    domain = self.request.get_host()
                    context["reset_url"] = f"{scheme}://{domain}{rel_url}"
        # Ensure current_year is present in the context
        if "current_year" not in context:
            context["current_year"] = datetime.now().year

        # Render the HTML email template
        html_template = render_to_string(
            "registration/password_reset_email.html", context
        )
        # Render the plain-text email template
        text_template = render_to_string(
            "registration/password_reset_email.txt", context
        )
        # Create the email message with both alternatives
        message = EmailMessage(
            subject,
            text_template,
            email_from,
            [to_email],
        )
        message.content_subtype = "text/plain"
        message.alternatives = [
            ("text/html", html_template)
        ]
        message.send()
