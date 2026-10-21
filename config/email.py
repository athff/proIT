"""Email backends with sanitized diagnostics for production delivery."""

import base64
import logging
import smtplib
import threading

import requests
from django.core.mail.backends.smtp import EmailBackend
from django.core.mail.backends.base import BaseEmailBackend

logger = logging.getLogger(__name__)

_email_backend_lock = threading.Lock()


class DiagnosticSMTPEmailBackend(EmailBackend):
    """Log sanitized SMTP connection failures before preserving Django errors."""

    def _log_failure(self, stage: str, error: Exception) -> None:
        # Extract SMTP response code/message if available, without logging credentials
        smtp_code = getattr(error, "smtp_code", None)
        smtp_message = getattr(error, "smtp_error", None) if smtp_code is not None else None

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
        # Acquire lock to ensure only one SMTP connection/Auth attempt at a time
        # This prevents Gmail from closing connections when multiple emails
        # are sent in rapid succession (common with password reset flows)
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
        super().__init__(fail_silently=fail_silently)
        self.api_key = kwargs.get("api_key", "").strip()
        self.from_email = kwargs.get("from_email", "").strip()
        self.timeout = kwargs.get("timeout", 30)
        self.api_url = kwargs.get("api_url", self.api_url).strip()

    def _log_failure(self, stage: str, error: Exception) -> None:
        logger.error(
            "Resend email %s failed: api_configured=%s sender_configured=%s "
            "timeout=%s error=%s",
            stage,
            bool(self.api_key),
            bool(self.from_email),
            self.timeout,
            type(error).__name__,
        )

    def _payload(self, message):
        payload = {
            "from": self.from_email or message.from_email,
            "to": message.to,
            "subject": message.subject,
            "text": message.body,
        }
        if getattr(message, "cc", None):
            payload["cc"] = message.cc
        if getattr(message, "bcc", None):
            payload["bcc"] = message.bcc
        if getattr(message, "reply_to", None):
            payload["reply_to"] = message.reply_to
        for alternative, mimetype in getattr(message, "alternatives", []):
            if mimetype == "text/html":
                payload["html"] = alternative
                break
        attachments = []
        for attachment in getattr(message, "attachments", []):
            if hasattr(attachment, "filename"):
                filename = attachment.filename
                content = attachment.content
            else:
                filename = attachment[0]
                content = attachment[1]
            if isinstance(content, str):
                content = content.encode()
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


