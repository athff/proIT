"""
URL configuration for config project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/6.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.contrib.auth import views as auth_views
from django.urls import include, path

from .views import dashboard
from .report_views import reports
from .auth_views import signup

AUTH_TEMPLATE_CONTEXT = {"is_auth_page": True}

urlpatterns = [
    path('admin/', admin.site.urls),
    path("", auth_views.LoginView.as_view(extra_context=AUTH_TEMPLATE_CONTEXT), name="login"),
    path("accounts/signup/", signup, name="signup"),
    path("accounts/logout/", auth_views.LogoutView.as_view(extra_context=AUTH_TEMPLATE_CONTEXT), name="logout"),
    path(
        "accounts/password_change/",
        auth_views.PasswordChangeView.as_view(extra_context=AUTH_TEMPLATE_CONTEXT),
        name="password_change",
    ),
    path(
        "accounts/password_change/done/",
        auth_views.PasswordChangeDoneView.as_view(extra_context=AUTH_TEMPLATE_CONTEXT),
        name="password_change_done",
    ),
    path(
        "accounts/password_reset/",
        auth_views.PasswordResetView.as_view(extra_context=AUTH_TEMPLATE_CONTEXT),
        name="password_reset",
    ),
    path(
        "accounts/password_reset/done/",
        auth_views.PasswordResetDoneView.as_view(extra_context=AUTH_TEMPLATE_CONTEXT),
        name="password_reset_done",
    ),
    path(
        "accounts/reset/<uidb64>/<token>/",
        auth_views.PasswordResetConfirmView.as_view(extra_context=AUTH_TEMPLATE_CONTEXT),
        name="password_reset_confirm",
    ),
    path(
        "accounts/reset/done/",
        auth_views.PasswordResetCompleteView.as_view(extra_context=AUTH_TEMPLATE_CONTEXT),
        name="password_reset_complete",
    ),
    path("accounts/", include("allauth.urls")),
    path("dashboard/", dashboard, name="dashboard"),
    path("reports/", reports, name="reports"),
    path("assets/", include("assets.urls")),
    path("people/", include("people.urls")),
    path("vendors/", include("vendors.urls")),
    path("dataio/", include("dataio.urls")),
]
