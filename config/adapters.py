from django.contrib import messages
from django.shortcuts import redirect
from allauth.socialaccount.adapter import DefaultSocialAccountAdapter
from allauth.core.exceptions import ImmediateHttpResponse


class SafeSocialAccountAdapter(DefaultSocialAccountAdapter):
    """Keep social sign-in from linking to an existing local account by email."""

    def pre_social_login(self, request, sociallogin):
        if sociallogin.is_existing:
            return
        email = (sociallogin.user.email or "").strip().lower()
        if email:
            from django.contrib.auth import get_user_model

            if get_user_model().objects.filter(email__iexact=email).exists():
                messages.error(
                    request,
                    "That email already has a proIT account. Sign in with your password first.",
                )
                raise ImmediateHttpResponse(redirect("login"))

    def populate_user(self, request, sociallogin, data):
        user = super().populate_user(request, sociallogin, data)
        user.is_staff = False
        user.is_superuser = False
        return user
