"""SMTP backend diagnostics that never include credential values."""

import logging
import smtplib

from django.core.mail.backends.smtp import EmailBackend

logger = logging.getLogger(__name__)


class DiagnosticSMTPEmailBackend(EmailBackend):
    """Log sanitized SMTP connection failures before preserving Django errors."""

    def _log_failure(self, stage: str, error: Exception) -> None:
        logger.error(
            "SMTP %s failed: host_configured=%s port=%s use_tls=%s "
            "use_ssl=%s timeout=%s error=%s",
            stage,
            bool(self.host),
            self.port,
            self.use_tls,
            self.use_ssl,
            self.timeout,
            type(error).__name__,
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
        try:
            return super().send_messages(email_messages)
        except smtplib.SMTPException as error:
            self._log_failure("message_delivery", error)
            raise
