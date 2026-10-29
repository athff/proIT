"""Authentication and dashboard tests."""

from io import BytesIO
import os
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.core import mail
from django.core.exceptions import ImproperlyConfigured
from django.test import TestCase, override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from django.template.loader import get_template
from unittest.mock import patch
from PIL import Image

from assets.models import Asset, AssetModel, Category, Manufacturer
from dataio.services.authorization import VIEWER, configure_role_groups
from people.models import Employee
from people.models import AccountProfile
from vendors.models import Vendor
from config.settings import (
    BASE_DIR,
    CONSOLE_EMAIL_BACKEND,
    RESEND_EMAIL_BACKEND,
    _allowed_hosts,
    _database_settings,
    _deployment_environment,
    _email_configuration,
    _mailers_configuration,
    _resolve_email_backend,
    _security_settings,
    _static_storage_backend,
    validate_production_configuration,
)



class AuthenticationTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="operator",
            email="operator@example.com",
            password="Initial-password-123",
        )

    def test_login_page_and_login_redirect(self):
        response = self.client.get(reverse("login"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, 'aria-label="Main navigation"')
        self.assertContains(response, reverse("google_login"))
        self.assertContains(response, "Continue with Google")
        self.assertContains(response, reverse("signup"))
        response = self.client.post(
            reverse("login"),
            {"username": "operator", "password": "Initial-password-123"},
        )
        self.assertRedirects(response, reverse("dashboard"))

    def test_signup_page_renders_registration_fields(self):
        response = self.client.get(reverse("signup"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Create your account")
        for field_name in ("first_name", "last_name", "username", "email", "password1", "password2"):
            self.assertContains(response, f'name="{field_name}"')
        self.assertContains(response, "signup.css")

    def test_signup_page_offers_google_sign_in(self):
        response = self.client.get(reverse("signup"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, reverse("google_login"))
        self.assertContains(response, "Continue with Google")

    def test_allauth_google_outcome_pages_use_proit_layout(self):
        for route_name, heading in (
            ("socialaccount_login_cancelled", "Sign-in cancelled"),
            ("socialaccount_login_error", "We couldn't sign you in"),
        ):
            response = self.client.get(reverse(route_name))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, heading)
            self.assertContains(response, "/static/css/oauth.css")
            self.assertContains(response, "/static/image/proit-logo.png")

    def test_allauth_templates_are_overridden_by_project_templates(self):
        for template_name in (
            "allauth/layouts/entrance.html",
            "socialaccount/login.html",
            "socialaccount/signup.html",
            "socialaccount/authentication_error.html",
            "socialaccount/login_cancelled.html",
            "socialaccount/login_redirect.html",
        ):
            template = get_template(template_name)
            self.assertTrue(
                template.origin.name.startswith(str(BASE_DIR / "templates")),
                f"{template_name} resolved to {template.origin.name}, "
                "not the project templates directory",
            )

    def test_signup_page_creates_standard_user_and_redirects_to_dashboard(self):
        response = self.client.post(
            reverse("signup"),
            {
                "first_name": "New",
                "last_name": "Operator",
                "username": "new-operator",
                "email": "new-operator@example.com",
                "password1": "New-secure-password-123",
                "password2": "New-secure-password-123",
            },
        )
        self.assertRedirects(response, reverse("dashboard"))
        user = get_user_model().objects.get(username="new-operator")
        self.assertTrue(user.check_password("New-secure-password-123"))
        self.assertEqual(user.first_name, "New")
        self.assertEqual(user.last_name, "Operator")
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertEqual(user.groups.count(), 0)
        self.assertTrue(response.wsgi_request.user.is_authenticated)

    @override_settings(
        AUTHENTICATION_BACKENDS=[
            "django.contrib.auth.backends.ModelBackend",
            "allauth.account.auth_backends.AuthenticationBackend",
        ]
    )
    def test_signup_logs_in_with_multiple_authentication_backends(self):
        response = self.client.post(
            reverse("signup"),
            {
                "first_name": "Backend",
                "last_name": "Test",
                "username": "backend-test",
                "email": "backend-test@example.com",
                "password1": "New-secure-password-123",
                "password2": "New-secure-password-123",
            },
        )

        self.assertRedirects(response, reverse("dashboard"))
        self.assertTrue(response.wsgi_request.user.is_authenticated)
        self.assertEqual(response.wsgi_request.user.username, "backend-test")

    def test_signup_rejects_invalid_passwords(self):
        response = self.client.post(
            reverse("signup"),
            {
                "first_name": "New",
                "last_name": "Operator",
                "username": "new-operator",
                "email": "new-operator@example.com",
                "password1": "short",
                "password2": "different",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("password2", response.context["form"].errors)

    def test_dashboard_redirects_anonymous_users_to_login(self):
        response = self.client.get(reverse("dashboard"))
        self.assertRedirects(
            response,
            "/accounts/login/?next=/dashboard/",
        )

    def test_root_redirects_anonymous_user_to_login(self):
        response = self.client.get("/")

        self.assertRedirects(response, reverse("login"))

    def test_root_redirects_authenticated_user_to_dashboard(self):
        self.client.force_login(self.user)

        response = self.client.get("/")

        self.assertRedirects(response, reverse("dashboard"))

    def test_account_dropdown_contains_connected_destinations(self):
        self.client.force_login(self.user)

        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, reverse("profile-account"))
        self.assertContains(response, reverse("password_change"))
        self.assertContains(response, reverse("assets:ticket-create"))
        self.assertContains(response, reverse("assets:ticket-list"))
        self.assertNotContains(response, reverse("admin-panel"))
        self.assertContains(response, "Signed in securely")

    def test_admin_account_dropdown_hides_end_user_ticket_actions(self):
        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save(update_fields=("is_staff", "is_superuser"))
        self.client.force_login(self.user)

        response = self.client.get(reverse("dashboard"))

        self.assertContains(response, reverse("admin-panel"))
        self.assertNotContains(response, reverse("assets:ticket-create"))
        self.assertNotContains(response, reverse("assets:ticket-list"))
        self.assertNotContains(response, "Raise support ticket")
        self.assertNotContains(response, "My tickets")

    def test_profile_update_saves_identity_and_processed_avatar(self):
        image_bytes = BytesIO()
        Image.new("RGB", (420, 260), "#2f6fed").save(image_bytes, format="PNG")
        avatar = SimpleUploadedFile(
            "avatar.png",
            image_bytes.getvalue(),
            content_type="image/png",
        )
        self.client.force_login(self.user)

        response = self.client.post(
            reverse("profile-account"),
            {
                "first_name": "Updated",
                "last_name": "Operator",
                "email": "updated-operator@example.com",
                "avatar": avatar,
            },
        )

        self.assertRedirects(response, reverse("profile-account"))
        self.user.refresh_from_db()
        self.assertEqual(self.user.get_full_name(), "Updated Operator")
        self.assertEqual(self.user.email, "updated-operator@example.com")
        profile = AccountProfile.objects.get(user=self.user)
        self.assertTrue(profile.avatar_data_uri.startswith("data:image/webp;base64,"))

    def test_admin_panel_is_restricted_and_shows_management_sections(self):
        self.client.force_login(self.user)
        self.assertEqual(self.client.get(reverse("admin-panel")).status_code, 403)

        self.user.is_staff = True
        self.user.is_superuser = True
        self.user.save(update_fields=("is_staff", "is_superuser"))
        response = self.client.get(reverse("admin-panel"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "User accounts")
        self.assertContains(response, "Roles &amp; permissions")
        self.assertContains(response, "System summary")
        self.assertContains(response, reverse("admin:auth_user_changelist"))

    def test_authenticated_user_can_access_dashboard(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("dashboard"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Dashboard")

    def test_logout_requires_post_and_csrf(self):
        self.client.force_login(self.user)
        response = self.client.get(reverse("logout"))
        self.assertEqual(response.status_code, 405)
        response = self.client.post(reverse("logout"))
        self.assertRedirects(response, reverse("login"))
        self.assertFalse(response.wsgi_request.user.is_authenticated)

    def test_password_change_updates_password(self):
        self.client.force_login(self.user)
        page = self.client.get(reverse("password_change"))
        self.assertEqual(page.status_code, 200)
        self.assertContains(page, "Change password")
        self.assertContains(page, "password.css")
        self.assertContains(page, 'data-password-toggle="id_old_password"')
        self.assertContains(page, 'data-password-toggle="id_new_password1"')
        self.assertContains(page, 'data-password-toggle="id_new_password2"')
        response = self.client.post(
            reverse("password_change"),
            {
                "old_password": "Initial-password-123",
                "new_password1": "Replacement-password-456",
                "new_password2": "Replacement-password-456",
            },
        )
        self.assertRedirects(response, reverse("password_change_done"))
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Replacement-password-456"))

    @override_settings(
        MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    )
    def test_password_reset_sends_email_for_known_address(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": "operator@example.com"},
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("password reset", mail.outbox[0].body.lower())

    @override_settings(
        MAILERS={"default": {"BACKEND": "django.core.mail.backends.locmem.EmailBackend"}}
    )
    def test_password_reset_does_not_reveal_unknown_address(self):
        response = self.client.post(
            reverse("password_reset"),
            {"email": "unknown@example.com"},
        )
        self.assertRedirects(response, reverse("password_reset_done"))
        self.assertEqual(len(mail.outbox), 0)

    def test_dataio_redirects_anonymous_users_to_login(self):
        response = self.client.get(
            reverse("csv-template", args=["departments"]),
        )
        self.assertRedirects(
            response,
            "/accounts/login/?next=/dataio/template/departments/",
        )

    def test_production_configuration_rejects_insecure_defaults(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_production_configuration(
                environment="production",
                secret_key="",
                debug=True,
                allowed_hosts=[],
                email_backend="django.core.mail.backends.console.EmailBackend",
            )

    def test_development_security_settings_remain_local(self):
        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            settings = _security_settings("development")
        self.assertFalse(settings["SECURE_SSL_REDIRECT"])
        self.assertFalse(settings["SESSION_COOKIE_SECURE"])
        self.assertFalse(settings["CSRF_COOKIE_SECURE"])
        self.assertEqual(settings["SECURE_HSTS_SECONDS"], 0)
        self.assertIsNone(settings["SECURE_PROXY_SSL_HEADER"])

    def test_production_security_settings_default_secure_except_hsts(self):
        with patch.dict(
            os.environ,
            {},
            clear=True,
        ):
            settings = _security_settings("production")
        self.assertTrue(settings["SECURE_SSL_REDIRECT"])
        self.assertTrue(settings["SESSION_COOKIE_SECURE"])
        self.assertTrue(settings["CSRF_COOKIE_SECURE"])
        self.assertEqual(settings["SECURE_HSTS_SECONDS"], 0)
        self.assertEqual(
            settings["SECURE_PROXY_SSL_HEADER"],
            ("HTTP_X_FORWARDED_PROTO", "https"),
        )

    def test_vercel_without_explicit_environment_uses_production(self):
        with patch.dict(
            os.environ,
            {"VERCEL": "1", "VERCEL_URL": "pro-it-peach.vercel.app"},
            clear=True,
        ):
            self.assertEqual(_deployment_environment(), "production")

    def test_vercel_hosts_are_trusted_https_origins(self):
        with patch.dict(
            os.environ,
            {"VERCEL_URL": "pro-it-peach.vercel.app"},
            clear=True,
        ):
            settings = _security_settings("production")
        self.assertIn(
            "https://pro-it-peach.vercel.app",
            settings["CSRF_TRUSTED_ORIGINS"],
        )

    def test_static_storage_uses_manifest_backend_only_in_production(self):
        from config import settings as project_settings

        self.assertEqual(
            _static_storage_backend("development"),
            "django.contrib.staticfiles.storage.StaticFilesStorage",
        )
        self.assertEqual(
            _static_storage_backend("production"),
            "whitenoise.storage.CompressedManifestStaticFilesStorage",
        )
        self.assertEqual(
            project_settings.STORAGES["staticfiles"]["BACKEND"],
            _static_storage_backend(project_settings.ENVIRONMENT),
        )
        self.assertNotEqual(project_settings.STATIC_ROOT, project_settings.BASE_DIR / "static")

    def test_email_configuration_reads_smtp_environment(self):
        with patch.dict(
            os.environ,
            {
                "PROIT_EMAIL_BACKEND": "django.core.mail.backends.smtp.EmailBackend",
                "EMAIL_HOST": "smtp.gmail.com",
                "EMAIL_PORT": "587",
                "EMAIL_HOST_USER": "sender@example.com",
                "EMAIL_HOST_PASSWORD": "test-app-password",
                "EMAIL_USE_TLS": "True",
                "DEFAULT_FROM_EMAIL": "sender@example.com",
            },
            clear=True,
        ):
            configuration = _email_configuration()

        self.assertEqual(configuration["host"], "smtp.gmail.com")
        self.assertEqual(configuration["port"], 587)
        self.assertTrue(configuration["use_tls"])
        self.assertFalse(configuration["use_ssl"])
        self.assertEqual(configuration["timeout"], 30)
        self.assertEqual(configuration["username"], "sender@example.com")

    def test_email_configuration_strips_surrounding_whitespace(self):
        with patch.dict(
            os.environ,
            {
                "EMAIL_HOST": " smtp.gmail.com ",
                "EMAIL_PORT": "587",
                "EMAIL_HOST_USER": " sender@example.com ",
                "EMAIL_HOST_PASSWORD": " app-password ",
                "EMAIL_USE_TLS": " true ",
                "EMAIL_USE_SSL": " false ",
                "EMAIL_TIMEOUT": "45",
            },
            clear=True,
        ):
            configuration = _email_configuration()

        self.assertEqual(configuration["host"], "smtp.gmail.com")
        self.assertEqual(configuration["username"], "sender@example.com")
        self.assertEqual(configuration["password"], "app-password")
        self.assertTrue(configuration["use_tls"])
        self.assertFalse(configuration["use_ssl"])
        self.assertEqual(configuration["timeout"], 45)

    def test_email_backend_short_names_expand_to_dotted_paths(self):
        self.assertEqual(_resolve_email_backend("resend"), RESEND_EMAIL_BACKEND)
        self.assertEqual(_resolve_email_backend("console"), CONSOLE_EMAIL_BACKEND)
        self.assertEqual(
            _resolve_email_backend("smtp"),
            "django.core.mail.backends.smtp.EmailBackend",
        )
        self.assertEqual(_resolve_email_backend(None), CONSOLE_EMAIL_BACKEND)
        # An explicit dotted path is passed through untouched.
        self.assertEqual(
            _resolve_email_backend("config.email.DiagnosticSMTPEmailBackend"),
            "config.email.DiagnosticSMTPEmailBackend",
        )

    def test_smtp_mailer_options_carry_connection_details(self):
        """Defining MAILERS disables EMAIL_*, so OPTIONS must be populated."""
        for backend in (
            "django.core.mail.backends.smtp.EmailBackend",
            "config.email.DiagnosticSMTPEmailBackend",
        ):
            with patch.dict(
                os.environ,
                {
                    "PROIT_EMAIL_BACKEND": backend,
                    "EMAIL_HOST": "smtp.gmail.com",
                    "EMAIL_PORT": "587",
                    "EMAIL_HOST_USER": "sender@example.com",
                    "EMAIL_HOST_PASSWORD": "app-password",
                    "EMAIL_USE_TLS": "True",
                },
                clear=True,
            ):
                options = _mailers_configuration(_email_configuration())["default"]["OPTIONS"]

            self.assertEqual(options["host"], "smtp.gmail.com")
            self.assertEqual(options["port"], 587)
            self.assertEqual(options["username"], "sender@example.com")
            self.assertEqual(options["password"], "app-password")
            self.assertTrue(options["use_tls"])
            self.assertFalse(options["use_ssl"])

    def test_resend_mailer_options_carry_api_credentials(self):
        with patch.dict(
            os.environ,
            {
                "PROIT_EMAIL_BACKEND": "resend",
                "RESEND_API_KEY": "re_test_key",
                "DEFAULT_FROM_EMAIL": "sender@example.com",
            },
            clear=True,
        ):
            mailers = _mailers_configuration(_email_configuration())

        self.assertEqual(mailers["default"]["BACKEND"], RESEND_EMAIL_BACKEND)
        self.assertEqual(mailers["default"]["OPTIONS"]["api_key"], "re_test_key")
        self.assertEqual(
            mailers["default"]["OPTIONS"]["from_email"], "sender@example.com"
        )

    def test_console_mailer_needs_no_options(self):
        with patch.dict(os.environ, {}, clear=True):
            mailers = _mailers_configuration(_email_configuration())

        self.assertEqual(mailers["default"]["BACKEND"], CONSOLE_EMAIL_BACKEND)
        self.assertEqual(mailers["default"]["OPTIONS"], {})

    def test_production_rejects_incomplete_smtp_diagnostic_backend(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_production_configuration(
                environment="production",
                secret_key="a-long-random-production-secret-key-value",
                debug=False,
                allowed_hosts=["example.com"],
                email_backend="config.email.DiagnosticSMTPEmailBackend",
            )

    def test_production_rejects_resend_without_api_key(self):
        with self.assertRaises(ImproperlyConfigured):
            validate_production_configuration(
                environment="production",
                secret_key="a-long-random-production-secret-key-value",
                debug=False,
                allowed_hosts=["example.com"],
                email_backend=RESEND_EMAIL_BACKEND,
                default_from_email="sender@example.com",
                email_api_key="",
            )

    def test_production_accepts_complete_configuration(self):
        validate_production_configuration(
            environment="production",
            secret_key="a-long-random-production-secret-key-value",
            debug=False,
            allowed_hosts=["example.com"],
            email_backend=RESEND_EMAIL_BACKEND,
            default_from_email="sender@example.com",
            email_api_key="re_live_key",
        )

    def test_database_url_requires_ssl_for_postgres(self):
        settings = _database_settings(
            "postgresql://user:password@db.example/neondb"
        )

        self.assertEqual(settings["ENGINE"], "django.db.backends.postgresql")
        self.assertEqual(settings["OPTIONS"]["sslmode"], "require")
        self.assertTrue(settings["CONN_HEALTH_CHECKS"])

    def test_database_url_accepts_pasted_vercel_value(self):
        settings = _database_settings(
            'DATABASE_URL="postgresql://user:password@db.example/neondb"'
        )

        self.assertEqual(settings["NAME"], "neondb")
        self.assertEqual(settings["HOST"], "db.example")
        self.assertEqual(settings["OPTIONS"]["sslmode"], "require")

    def test_allowed_hosts_include_vercel_runtime_hostnames(self):
        with patch.dict(
            os.environ,
            {
                "ALLOWED_HOSTS": "custom.example.com,custom.example.com",
                "VERCEL_URL": "pro-it-peach.vercel.app",
                "VERCEL_PROJECT_PRODUCTION_URL": "proit.vercel.app",
                "VERCEL_BRANCH_URL": "proit-git-master.vercel.app",
            },
            clear=True,
        ):
            self.assertEqual(
                _allowed_hosts(),
                [
                    "custom.example.com",
                    "pro-it-peach.vercel.app",
                    "proit.vercel.app",
                    "proit-git-master.vercel.app",
                ],
            )


class DashboardDataTests(TestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(
            username="dashboard-user",
            password="Initial-password-123",
        )
        self.client.force_login(self.user)

    def test_dashboard_uses_real_metrics_and_status_counts(self):
        category = Category.objects.create(name="Laptops")
        manufacturer = Manufacturer.objects.create(name="Acme")
        asset_model = AssetModel.objects.create(
            name="Pro 14",
            manufacturer=manufacturer,
            category=category,
        )
        Employee.objects.create(
            employee_id="EMP-DASH-1",
            first_name="Ada",
            last_name="Lovelace",
            email="dash@example.com",
        )
        Vendor.objects.create(company_name="Dashboard Vendor")
        Asset.objects.create(
            asset_tag="DASH-1",
            serial_number="DASH-SN-1",
            model=asset_model,
            status=Asset.Status.AVAILABLE,
        )
        Asset.objects.create(
            asset_tag="DASH-2",
            serial_number="DASH-SN-2",
            model=asset_model,
            status=Asset.Status.MAINTENANCE,
        )

        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.context["asset_count"], 2)
        self.assertEqual(response.context["employee_count"], 1)
        self.assertEqual(response.context["vendor_count"], 1)
        self.assertEqual(response.context["available_count"], 1)
        self.assertEqual(response.context["maintenance_count"], 1)
        self.assertContains(response, "DASH-1")
        self.assertContains(response, "DASH-2")

    def test_dashboard_empty_state_is_graceful(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.context["asset_count"], 0)
        self.assertContains(response, "No assets have been added yet.")
        self.assertContains(response, "No recent assets to display.")
        self.assertContains(response, "Activity will appear as assets are added.")

    def test_viewer_actions_follow_rbac(self):
        configure_role_groups()
        self.user.groups.add(Group.objects.get(name=VIEWER))

        response = self.client.get(reverse("dashboard"))

        self.assertTrue(response.context["can_export_assets"])
        self.assertFalse(response.context["can_import_assets"])
        self.assertContains(response, "Export assets")
        self.assertNotContains(response, "Import assets")

    def test_summary_cards_link_to_authorized_destinations(self):
        self.user.is_superuser = True
        self.user.save(update_fields=["is_superuser"])

        response = self.client.get(reverse("dashboard"))
        content = response.content.decode()

        self.assertIn('href="/assets/"', content)
        self.assertIn('href="/people/employees/"', content)
        self.assertIn('href="/vendors/"', content)
        self.assertIn('href="/assets/?status=available"', content)
        self.assertIn('href="/assets/?status=maintenance"', content)
