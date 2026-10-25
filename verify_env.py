import os
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from config.settings import EMAIL_CONFIGURATION

print("EMAIL_CONFIGURATION keys:", list(EMAIL_CONFIGURATION.keys()))
print("host:", EMAIL_CONFIGURATION["host"])
print("port:", EMAIL_CONFIGURATION["port"])
print("username:", EMAIL_CONFIGURATION["username"])
print("use_tls:", EMAIL_CONFIGURATION["use_tls"])
print("use_ssl:", EMAIL_CONFIGURATION["use_ssl"])
print("timeout:", EMAIL_CONFIGURATION["timeout"])

# Check password presence without exposing it
password = EMAIL_CONFIGURATION["password"]
if password:
    print("EMAIL_HOST_PASSWORD: PRESENT (16-char App Password expected)")
else:
    print("EMAIL_HOST_PASSWORD: MISSING or EMPTY")

# Verify backend
from django.conf import settings
print("\nDefault EMAIL_BACKEND:", getattr(settings, 'EMAIL_BACKEND', 'NOT SET'))

# Check if DiagnosticSMTPEmailBackend is importable
try:
    from config.email import DiagnosticSMTPEmailBackend
    print("DiagnosticSMTPEmailBackend: IMPORTABLE")
except ImportError as e:
    print("DiagnosticSMTPEmailBackend: IMPORT ERROR -", e)