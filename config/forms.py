"""Project-level authentication forms."""

import base64
from io import BytesIO

from django import forms
from django.contrib.auth import get_user_model
from django.contrib.auth.forms import PasswordResetForm, UserCreationForm
from django.db import transaction
from PIL import Image, ImageOps, UnidentifiedImageError

from people.models import AccountProfile


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


class ProITPasswordResetForm(PasswordResetForm):
    """Build password-reset links from the request's current host."""

    def save(self, *args, domain_override=None, request=None, **kwargs):
        if domain_override is None and request is not None:
            domain_override = request.get_host()
        return super().save(
            *args,
            domain_override=domain_override,
            request=request,
            **kwargs,
        )


class AccountProfileForm(forms.Form):
    """Update account identity fields and a compact database-backed avatar."""

    MAX_AVATAR_SIZE = 2 * 1024 * 1024

    first_name = forms.CharField(max_length=150, label="First name")
    last_name = forms.CharField(max_length=150, label="Last name")
    email = forms.EmailField(max_length=254, label="Email address")
    avatar = forms.ImageField(required=False, label="Profile photo")
    remove_avatar = forms.BooleanField(required=False, label="Remove current photo")

    def __init__(self, *args, user, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        if not self.is_bound:
            self.initial.update(
                {
                    "first_name": user.first_name,
                    "last_name": user.last_name,
                    "email": user.email,
                }
            )
        for name in ("first_name", "last_name", "email", "avatar"):
            self.fields[name].widget.attrs.setdefault("class", "account-input")
        self.fields["avatar"].widget.attrs["accept"] = "image/png,image/jpeg,image/webp"

    def clean_email(self):
        email = self.cleaned_data["email"].strip().lower()
        if (
            get_user_model()
            .objects.filter(email__iexact=email)
            .exclude(pk=self.user.pk)
            .exists()
        ):
            raise forms.ValidationError("An account already uses this email address.")
        return email

    def clean_avatar(self):
        avatar = self.cleaned_data.get("avatar")
        if avatar and avatar.size > self.MAX_AVATAR_SIZE:
            raise forms.ValidationError("Choose an image smaller than 2 MB.")
        return avatar

    @staticmethod
    def _avatar_data_uri(upload):
        try:
            image = Image.open(upload)
            image = ImageOps.exif_transpose(image).convert("RGB")
            image = ImageOps.fit(image, (256, 256), method=Image.Resampling.LANCZOS)
        except (UnidentifiedImageError, OSError, ValueError) as error:
            raise forms.ValidationError("Upload a valid PNG, JPEG, or WebP image.") from error
        output = BytesIO()
        image.save(output, format="WEBP", quality=85, method=6)
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        return f"data:image/webp;base64,{encoded}"

    @transaction.atomic
    def save(self):
        self.user.first_name = self.cleaned_data["first_name"].strip()
        self.user.last_name = self.cleaned_data["last_name"].strip()
        self.user.email = self.cleaned_data["email"]
        self.user.save(update_fields=("first_name", "last_name", "email"))

        profile, _ = AccountProfile.objects.get_or_create(user=self.user)
        if self.cleaned_data.get("remove_avatar"):
            profile.avatar_data_uri = ""
        elif self.cleaned_data.get("avatar"):
            profile.avatar_data_uri = self._avatar_data_uri(self.cleaned_data["avatar"])
        profile.save()
        return profile
