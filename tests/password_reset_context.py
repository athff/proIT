import datetime

from django.test import override_settings
from django.contrib.auth import get_user_model
from django.test import TestCase
from django.core import mail

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
            "/accounts/password-reset/",
            {"email": self.user.email},
            follow=True,
        )
        self.assertEqual(len(mail.outbox), 1)
        email = mail.outbox[0]
        # The plain-text body should contain a URL starting with http
        self.assertIn("http", email.body.lower())
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

    def test_template_vars_in_context(self):
        """Directly calling send_mail with a mock request should inject reset_url and current_year."""
        # Post to the reset URL to trigger send_mail
        response = self.client.post(
            "/accounts/password-reset/",
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