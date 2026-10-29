from django.contrib import messages
from django.contrib.auth import authenticate, login
from django.shortcuts import redirect, render

from .forms import SignUpForm


def signup(request):
    if request.user.is_authenticated:
        return redirect("dashboard")
    form = SignUpForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        authenticated_user = authenticate(
            request,
            username=user.get_username(),
            password=form.cleaned_data["password1"],
        )
        if authenticated_user is None:
            # The account was created successfully, but no configured backend
            # accepted its credentials. Keep the user on a safe sign-in path
            # instead of raising an error after the database insert.
            messages.info(
                request,
                "Your account was created. Please sign in to continue.",
            )
            return redirect("login")
        login(request, authenticated_user)
        messages.success(request, "Your proIT account was created.")
        return redirect("dashboard")
    return render(
        request,
        "registration/signup.html",
        {"form": form, "is_auth_page": True},
    )
