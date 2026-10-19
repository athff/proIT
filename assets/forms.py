"""Forms for the authenticated Assets workspace."""

from django import forms

from people.models import Employee
from .models import Asset


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
