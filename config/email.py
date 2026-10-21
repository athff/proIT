"""Email backends with sanitized diagnostics for production delivery."""

import base64
import logging
import smtplib
import threading

import requests
from django.core.exceptions import ImproperlyConfigured
from django.core.mail.backends.base import BaseEmailBackend
from django.core.mail.backends.smtp import EmailBackend

logger = logging.getLogger(__name__)

# Only serializes sends inside a single process. On serverless platforms each
# container has its own lock, so this does not limit overall concurrency.
_email_backend_lock = threading.Lock()

DEFAULT_TIMEOUT = 10


class DiagnosticSMTPEmailBackend(EmailBackend):
    """Log sanitized SMTP connection failures before preserving Django errors."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Never wait forever on a mail server inside a web request.
        if self.timeout is None:
            self.timeout = DEFAULT_TIMEOUT

    def _log_failure(self, stage: str, error: Exception) -> None:
        # Mark the error so the same failure is not logged twice
        # (open() is called from inside send_messages()).
        if getattr(error, "_diagnostic_logged", False):
            return
        try:
            error._diagnostic_logged = True
        except AttributeError:
            pass

        smtp_code = getattr(error, "smtp_code", None)
        smtp_message = getattr(error, "smtp_error", None) if smtp_code is not None else None
        if isinstance(smtp_message, bytes):
            smtp_message = smtp_message.decode("utf-8", "replace")

        logger.error(
            "SMTP %s failed: host_configured=%s port=%s use_tls=%s "
            "use_ssl=%s timeout=%s error=%s[%s]",
            stage,
            bool(self.host),
            self.port,
            self.use_tls,
            self.use_ssl,
            self.timeout,
            type(error).__name__,
            f"{smtp_code}: {smtp_message}" if smtp_message else type(error).__name__,
        )

    def open(self):
        try:
            return super().open()
        except smtplib.SMTPAuthenticationError as error:
            self._log_failure("authentication", error)
            raise
        except smtplib.SMTPServerDisconnected as error:
            self._log_failure("connection_or_authentication", error)
            raise
        except OSError as error:
            self._log_failure("connection", error)
            raise

    def send_messages(self, email_messages):
        with _email_backend_lock:
            try:
                return super().send_messages(email_messages)
            except smtplib.SMTPException as error:
                self._log_failure("message_delivery", error)
                raise


class ResendEmailBackend(BaseEmailBackend):
    """Deliver Django email messages through Resend's HTTPS API."""

    api_url = "https://api.resend.com/emails"

    def __init__(self, fail_silently=False, **kwargs):
        # Django 6.x creates backends as backend_class(alias=alias, **options).
        alias = kwargs.pop("alias", None)
        try:
            super().__init__(alias=alias, fail_silently=fail_silently)
        except TypeError:
            super().__init__(fail_silently=fail_silently)

        self.api_key = (kwargs.get("api_key") or "").strip()
        self.from_email = (kwargs.get("from_email") or "").strip()
        self.timeout = kwargs.get("timeout") or DEFAULT_TIMEOUT
        self.api_url = (kwargs.get("api_url") or self.api_url).strip()

        if not self.api_key:
            raise ImproperlyConfigured("Resend api_key is not configured.")

    def _log_failure(self, stage: str, error: Exception) -> None:
        # Resend explains rejections in the response body (for example
        # "domain is not verified"). Use `is not None`: a Response object is
        # falsy for 4xx/5xx statuses.
        response = getattr(error, "response", None)
        status = response.status_code if response is not None else None
        detail = response.text[:300] if response is not None else ""
        logger.error(
            "Resend email %s failed: api_configured=%s sender_configured=%s "
            "timeout=%s error=%s status=%s detail=%s",
            stage,
            bool(self.api_key),
            bool(self.from_email),
            self.timeout,
            type(error).__name__,
            status,
            detail,
        )

    @staticmethod
    def _attachment_parts(attachment):
        """Return (filename, bytes) for tuple or MIMEBase attachments."""
        if hasattr(attachment, "filename"):
            filename = attachment.filename
            content = attachment.content
        elif hasattr(attachment, "get_payload"):
            filename = attachment.get_filename() or "attachment"
            content = attachment.get_payload(decode=True) or b""
        else:
            filename = attachment[0]
            content = attachment[1]
        if isinstance(content, str):
            content = content.encode()
        return filename, content

    def _payload(self, message):
        to = list(message.to or [])
        cc = list(getattr(message, "cc", None) or [])
        bcc = list(getattr(message, "bcc", None) or [])

        # Resend requires at least one "to" address. If the message only has
        # cc/bcc recipients, promote one of them so the request is accepted.
        if not to:
            if cc:
                to, cc = cc, []
            elif bcc:
                to, bcc = bcc, []

        payload = {
            "from": self.from_email or message.from_email,
            "to": to,
            "subject": message.subject,
            "text": message.body,
        }
        if cc:
            payload["cc"] = cc
        if bcc:
            payload["bcc"] = bcc
        if getattr(message, "reply_to", None):
            payload["reply_to"] = message.reply_to

        for alternative, mimetype in getattr(message, "alternatives", []):
            if mimetype == "text/html":
                payload["html"] = alternative
                break

        attachments = []
        for attachment in getattr(message, "attachments", []):
            filename, content = self._attachment_parts(attachment)
            attachments.append(
                {
                    "filename": filename,
                    "content": base64.b64encode(content).decode("ascii"),
                }
            )
        if attachments:
            payload["attachments"] = attachments
        return payload

    def _send(self, message):
        if not message.recipients():
            return False
        try:
            response = requests.post(
                self.api_url,
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                json=self._payload(message),
                timeout=self.timeout,
            )
            response.raise_for_status()
        except requests.RequestException as error:
            self._log_failure("delivery", error)
            if self.fail_silently:
                return False
            raise
        return True

    def send_messages(self, email_messages):
        sent = 0
        for message in email_messages:
            if self._send(message):
                sent += 1
        return sent