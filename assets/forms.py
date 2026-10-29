"""Forms for the authenticated Assets workspace."""

import base64
from io import BytesIO

from django import forms
from django.contrib.auth import get_user_model
from PIL import Image, ImageOps, UnidentifiedImageError

from dataio.services.authorization import ADMINISTRATOR, is_role
from people.models import Employee
from .models import Asset, SupportTicket


class AssetForm(forms.ModelForm):
    class Meta:
        model = Asset
        fields = (
            "asset_tag",
            "serial_number",
            "model",
            "vendor",
            "location",
            "assigned_employee",
            "status",
            "purchase_date",
            "purchase_cost",
            "warranty_expiry",
            "notes",
        )
        widgets = {
            "purchase_date": forms.DateInput(attrs={"type": "date"}),
            "warranty_expiry": forms.DateInput(attrs={"type": "date"}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "form-control")
        self.fields["model"].queryset = self.fields["model"].queryset.select_related(
            "manufacturer", "category"
        )
        self.fields["assigned_employee"].label = "Assigned employee"

    def clean(self):
        cleaned = super().clean()
        employee = cleaned.get("assigned_employee")
        status = cleaned.get("status")
        if employee is not None and status != Asset.Status.ASSIGNED:
            self.add_error(
                "status",
                "Assets with an assigned employee must use status Assigned.",
            )
        if status == Asset.Status.ASSIGNED and employee is None:
            self.add_error(
                "assigned_employee",
                "Assigned assets require an employee.",
            )
        return cleaned


class AssetAssignmentForm(forms.Form):
    asset = forms.ModelChoiceField(
        queryset=Asset.objects.none(),
        label="Asset",
        empty_label="Select an available asset",
    )
    employee = forms.ModelChoiceField(
        queryset=Employee.objects.none(),
        label="Employee",
        empty_label="Select an employee",
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["asset"].queryset = (
            Asset.objects.filter(
                assigned_employee__isnull=True,
                status=Asset.Status.AVAILABLE,
            )
            .select_related("model__manufacturer")
            .order_by("asset_tag")
        )
        self.fields["employee"].queryset = Employee.objects.filter(
            is_active=True
        ).select_related("department").order_by("last_name", "first_name")


class TicketAssetChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, asset):
        return f"{asset.asset_tag} · {asset.model} · {asset.serial_number}"


class SupportTicketForm(forms.ModelForm):
    MAX_ATTACHMENT_SIZE = 3 * 1024 * 1024

    asset = TicketAssetChoiceField(queryset=Asset.objects.none())
    attachment = forms.ImageField(
        required=False,
        label="Screenshot or photo (optional)",
    )

    class Meta:
        model = SupportTicket
        fields = ("asset", "description", "priority")
        widgets = {
            "description": forms.Textarea(
                attrs={
                    "rows": 6,
                    "placeholder": "Describe what is not working, when it started, and anything you already tried.",
                }
            ),
            "priority": forms.RadioSelect,
        }

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        assets = Asset.objects.select_related("model__manufacturer").order_by("asset_tag")
        if not is_role(user, ADMINISTRATOR):
            assets = assets.filter(assigned_employee__email__iexact=user.email)
        self.fields["asset"].queryset = assets
        self.fields["asset"].empty_label = "Select your assigned asset"
        self.fields["asset"].widget.attrs["class"] = "ticket-input"
        self.fields["description"].widget.attrs["class"] = "ticket-input"
        self.fields["attachment"].widget.attrs.update(
            {
                "class": "ticket-input",
                "accept": "image/png,image/jpeg,image/webp",
            }
        )

    def clean_attachment(self):
        attachment = self.cleaned_data.get("attachment")
        if attachment and attachment.size > self.MAX_ATTACHMENT_SIZE:
            raise forms.ValidationError("Choose an image smaller than 3 MB.")
        return attachment

    @staticmethod
    def _attachment_data_uri(upload):
        try:
            image = Image.open(upload)
            image = ImageOps.exif_transpose(image).convert("RGB")
            image.thumbnail((1400, 1400), Image.Resampling.LANCZOS)
        except (UnidentifiedImageError, OSError, ValueError) as error:
            raise forms.ValidationError("Upload a valid PNG, JPEG, or WebP image.") from error
        output = BytesIO()
        image.save(output, format="WEBP", quality=82, method=6)
        return "data:image/webp;base64," + base64.b64encode(output.getvalue()).decode("ascii")

    def save(self, commit=True):
        ticket = super().save(commit=False)
        ticket.requester = self.user
        attachment = self.cleaned_data.get("attachment")
        if attachment:
            ticket.attachment_data_uri = self._attachment_data_uri(attachment)
            ticket.attachment_name = attachment.name[:255]
        if commit:
            ticket.save()
        return ticket


class AdminTicketUpdateForm(forms.ModelForm):
    class Meta:
        model = SupportTicket
        fields = ("status", "assigned_to", "admin_notes", "resolution")
        widgets = {
            "admin_notes": forms.Textarea(attrs={"rows": 4}),
            "resolution": forms.Textarea(attrs={"rows": 4}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["assigned_to"].queryset = get_user_model().objects.filter(
            is_active=True,
            is_staff=True,
        ).order_by("username")
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "ticket-input")
