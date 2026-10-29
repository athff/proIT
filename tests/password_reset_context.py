import datetime

from django.contrib.auth.tokens import default_token_generator
from django.test import override_settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.core import mail
from django.urls import reverse
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from config.views import ProITPasswordResetView

User = get_user_model()


@override_settings(EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class PasswordResetContextTest(TestCase):
    """Verify that send_mail injects reset_url and current_year correctly."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="testuser",
            email="test@example.com",
            password="password123",
        )

    def test_reset_url_and_year_in_mail_outbox(self):
        """After a password-reset request the e-mail contains a URL and the year."""
        response = self.client.post(
            "/accounts/password_reset/",
            {"email": self.user.email},
            follow=True,
        )
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        # The plain-text body should contain a URL and must not contain HTML.
        self.assertIn("http", email.body.lower())
        self.assertNotIn("<!doctype html>", email.body.lower())
        # The HTML alternatives should also contain a URL
        html_content = None
        for content, mimetype in email.alternatives:
            if mimetype == "text/html":
                html_content = content
                break
        self.assertIsNotNone(html_content, "HTML alternative should be present")
        self.assertIn("http", html_content.lower())
        # The year should appear in both bodies
        self.assertIn(str(datetime.date.today().year), email.body)
        self.assertIn(str(datetime.date.today().year), html_content)
        self.assertIn("http://testserver/accounts/reset/", email.body)
        self.assertIn("http://testserver/accounts/reset/", html_content)
        self.assertEqual(email.message().get_content_type(), "multipart/alternative")

    def test_template_vars_in_context(self):
        """Directly calling send_mail with a mock request should inject reset_url and current_year."""
        # Post to the reset URL to trigger send_mail
        response = self.client.post(
            "/accounts/password_reset/",
            {"email": self.user.email},
            follow=False,
        )
        # The view's send_mail was called; check that the email was sent
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        # Verify URL and year are present
        self.assertIn("http", email.body.lower())
        html_content = None
        for content, mimetype in email.alternatives:
            if mimetype == "text/html":
                html_content = content
                break
        self.assertIsNotNone(html_content)
        self.assertIn("http", html_content.lower())
        self.assertIn(str(datetime.date.today().year), email.body)
        self.assertIn(str(datetime.date.today().year), html_content)

    def test_reset_link_changes_password_and_allows_login(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        token = default_token_generator.make_token(self.user)
        reset_url = reverse(
            "password_reset_confirm",
            kwargs={"uidb64": uid, "token": token},
        )

        response = self.client.get(reset_url, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Reset your password")
        self.assertContains(response, 'name="new_password1"')
        self.assertContains(response, 'name="new_password2"')
        self.assertContains(response, "Change password")

        confirmation_url = response.request["PATH_INFO"]
        response = self.client.post(
            confirmation_url,
            {
                "new_password1": "Replacement-password-456",
                "new_password2": "Replacement-password-456",
            },
            follow=True,
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Password changed successfully")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Replacement-password-456"))
        self.assertFalse(self.user.check_password("password123"))

        login_response = self.client.post(
            reverse("login"),
            {
                "username": self.user.username,
                "password": "Replacement-password-456",
            },
        )
        self.assertRedirects(login_response, reverse("dashboard"))
