"""Forms for the authenticated People workspace."""

from django import forms

from .models import Department, Employee, Location


class DepartmentForm(forms.ModelForm):
    class Meta:
        model = Department
        fields = ("name", "description", "is_active")
        widgets = {"description": forms.Textarea(attrs={"rows": 4})}


class LocationForm(forms.ModelForm):
    class Meta:
        model = Location
        fields = ("name", "address", "city", "region", "country", "is_active")
        widgets = {"address": forms.Textarea(attrs={"rows": 3})}


class EmployeeForm(forms.ModelForm):
    class Meta:
        model = Employee
        fields = (
            "employee_id",
            "first_name",
            "last_name",
            "email",
            "department",
            "location",
            "is_active",
        )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["department"].queryset = Department.objects.order_by("name")
        self.fields["location"].queryset = Location.objects.order_by("name")
