from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import UserCreationForm


class SignUpForm(UserCreationForm):
    email = forms.EmailField(required=True, label="Work email")
    first_name = forms.CharField(required=True, label="First name")
    last_name = forms.CharField(required=True, label="Last name")

    class Meta(UserCreationForm.Meta):
        model = get_user_model()
        fields = ("first_name", "last_name", "username", "email")

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Username"
        self.fields["username"].help_text = "Use a short name you will recognize."
        self.fields["email"].help_text = "Use your work email address."
        self.fields["password1"].label = "Password"
        self.fields["password2"].label = "Confirm password"
        for field in self.fields.values():
            field.widget.attrs.setdefault("class", "auth-input")
