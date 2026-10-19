"""Forms for the authenticated Vendor workspace."""

from django import forms

from .models import Vendor


class VendorForm(forms.ModelForm):
    class Meta:
        model = Vendor
        fields = (
            "company_name",
            "contact_name",
            "email",
            "phone",
            "website",
            "address",
            "notes",
            "is_active",
        )
        widgets = {
            "address": forms.Textarea(attrs={"rows": 3}),
            "notes": forms.Textarea(attrs={"rows": 4}),
        }
