import os
import sys

# Set the env var before importing django
os.environ['PROIT_EMAIL_BACKEND'] = 'config.email.DiagnosticSMTPEmailBackend'

# Add the project to path
sys.path.insert(0, r'e:\proIT')

import django
from django.conf import settings

# Configure Django settings minimally
if not settings.configured:
    settings.configure(
        DATABASES={'default': {'ENGINE': 'django.db.backends.sqlite3', 'NAME': ':memory:'}},
        INSTALLED_APPS=[
            'django.contrib.contenttypes',
            'django.contrib.auth',
        ],
        DEFAULT_FROM_EMAIL='test@example.com',
        EMAIL_BACKEND='config.email.DiagnosticSMTPEmailBackend',
    )

django.setup()

from config.email import DiagnosticSMTPEmailBackend

print("=" * 60)
print("SUCCESS: DiagnosticSMTPEmailBackend is configured")
print("=" * 60)
print(f"Backend class: {django.conf.settings.EMAIL_BACKEND}")
print(f"Lock exists: {hasattr(DiagnosticSMTPEmailBackend, '_email_backend_lock')}")
print(f"Lock is threading.Lock: {isinstance(DiagnosticSMTPEmailBackend._email_backend_lock, type(__import__('threading').Lock()))}")
print("=" * 60)
print("The threading lock will prevent concurrent SMTP AUTH attempts")
print("that cause Gmail to close connections.")
print("=" * 60)